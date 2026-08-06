#!/usr/bin/env python3
"""
vault.py — Personal Encrypted Vault
AES-256-GCM encryption with Argon2id key derivation.

Usage:
  python vault.py encrypt <file_or_folder> [--out vault.vlt]
  python vault.py decrypt <vault_file>     [--out restored]
  python vault.py list    <vault_file>
  python vault.py verify  <vault_file>
"""

import argparse
import datetime
import getpass
import io
import json
import os
import shutil
import struct
import sys
import tarfile
import time
from pathlib import Path

# ---- Tool Metadata ----
TOOL_NAME = "Personal Vault"
TOOL_VERSION = "1.1.0"

# ---- Format constants ----
MAGIC_V1       = b"VAULT01\x00"
MAGIC_V2       = b"VAULT02\x00"
MAGIC          = MAGIC_V2
SALT_LEN       = 16
NONCE_LEN      = 12
KEY_LEN        = 32
CHUNK_SIZE     = 64 * 1024          # 64 KiB per chunk
ARGON2_TIME    = 3
ARGON2_MEM     = 64 * 1024          # 64 MiB
ARGON2_PARA    = 4

# V1 Header: MAGIC(8) | salt(16) | time(4) | mem(4) | para(4) | chunk_count(8)
HEADER_FMT_V1  = ">8s16sIIIQ"
HEADER_SIZE_V1 = struct.calcsize(HEADER_FMT_V1)

# V2 Header: MAGIC(8) | salt(16) | time(4) | mem(4) | para(4) | chunk_count(8) | meta_len(4)
HEADER_FMT_V2  = ">8s16sIIIQI"
HEADER_SIZE_V2 = struct.calcsize(HEADER_FMT_V2)

HEADER_FMT     = HEADER_FMT_V2
HEADER_SIZE    = HEADER_SIZE_V2


# ------------------------------------------------------------------
# Terminal UI & Color Formatting
# ------------------------------------------------------------------
class Colors:
    CYAN    = "\033[96m"
    GREEN   = "\033[92m"
    YELLOW  = "\033[93m"
    RED     = "\033[91m"
    BLUE    = "\033[94m"
    BOLD    = "\033[1m"
    DIM     = "\033[2m"
    RESET   = "\033[0m"

    @classmethod
    def check_tty(cls):
        """Disable color escape codes if output is not a TTY or NO_COLOR is set."""
        if not sys.stdout.isatty() or os.environ.get("NO_COLOR"):
            cls.CYAN = ""
            cls.GREEN = ""
            cls.YELLOW = ""
            cls.RED = ""
            cls.BLUE = ""
            cls.BOLD = ""
            cls.DIM = ""
            cls.RESET = ""


Colors.check_tty()


def print_banner():
    """Display the tool name, version, and cryptographic summary banner."""
    print(f"""{Colors.BOLD}{Colors.CYAN}
 ╔════════════════════════════════════════════════════════════════════════════╗
 ║   🔒 {TOOL_NAME.upper()} (v{TOOL_VERSION}) — Encrypted Archive CLI                      ║
 ║   AES-256-GCM Authenticated Encryption  •  Argon2id Key Derivation (64MB)  ║
 ╚════════════════════════════════════════════════════════════════════════════╝{Colors.RESET}""")


def get_cli_name() -> str:
    """Detect if running via symlink/tool name (e.g. 'vault') or 'python3 vault.py'."""
    prog = Path(sys.argv[0]).name
    if prog.endswith(".py"):
        return f"python3 {prog}"
    return prog


def show_general_help():
    """Display comprehensive tool description, commands overview, and examples."""
    cli = get_cli_name()
    print_banner()
    print(f"""
{Colors.BOLD}DESCRIPTION:{Colors.RESET}
  {Colors.BOLD}{TOOL_NAME}{Colors.RESET} is a high-security CLI utility for encrypting files and entire
  directories into tamper-evident {Colors.CYAN}.vlt{Colors.RESET} archives.

  • {Colors.BOLD}Argon2id KDF{Colors.RESET}: Memory-hard key derivation (64 MiB, 3 iterations)
    designed to resist GPU and ASIC brute-force attacks.
  • {Colors.BOLD}AES-256-GCM{Colors.RESET}: Authenticated symmetric encryption in 64 KiB chunks
    guaranteeing both confidentiality and tamper detection.
  • {Colors.BOLD}Directory Archiving{Colors.RESET}: Automatically preserves directory structures,
    file permissions, and nested hierarchies.

{Colors.BOLD}USAGE:{Colors.RESET}
  {Colors.GREEN}{cli} <command> [arguments] [options]{Colors.RESET}
  {Colors.GREEN}{cli} help [command]{Colors.RESET}

{Colors.BOLD}AVAILABLE COMMANDS:{Colors.RESET}
  {Colors.CYAN}encrypt{Colors.RESET}  <target> [--out <dest>] [--wipe] [--keep]
                                    Encrypt file/folder (interactive delete prompt,
                                    or --wipe to shred immediately)
  {Colors.CYAN}decrypt{Colors.RESET}  <vault>  [--out <dest>]   Decrypt and restore files or folder
  {Colors.CYAN}list{Colors.RESET}     <vault>                   Inspect contents of a vault without extracting
  {Colors.CYAN}verify{Colors.RESET}   <vault>                   Verify chunk integrity and password
  {Colors.CYAN}help{Colors.RESET}     [command]                 Show detailed guide and practical examples

{Colors.BOLD}QUICK EXAMPLES:{Colors.RESET}
  {Colors.DIM}# 1. Encrypt an entire directory into my_docs.vlt (asks to delete original):{Colors.RESET}
  {Colors.GREEN}{cli} encrypt /path/to/my_docs{Colors.RESET}

  {Colors.DIM}# 2. Encrypt and automatically shred original files:{Colors.RESET}
  {Colors.GREEN}{cli} encrypt /path/to/my_docs --wipe{Colors.RESET}

  {Colors.DIM}# 3. Encrypt a single file with custom output name:{Colors.RESET}
  {Colors.GREEN}{cli} encrypt secret.pdf --out backup.vlt{Colors.RESET}

  {Colors.DIM}# 4. Inspect files inside a vault without saving to disk:{Colors.RESET}
  {Colors.GREEN}{cli} list my_docs.vlt{Colors.RESET}

  {Colors.DIM}# 5. Decrypt and restore to a target directory:{Colors.RESET}
  {Colors.GREEN}{cli} decrypt my_docs.vlt --out restored_folder/{Colors.RESET}

  {Colors.DIM}# 6. Check if a vault is intact and password is valid:{Colors.RESET}
  {Colors.GREEN}{cli} verify my_docs.vlt{Colors.RESET}

{Colors.DIM}For detailed guide on a specific command:{Colors.RESET}
  {Colors.YELLOW}{cli} help <command>{Colors.RESET}  (e.g. {Colors.YELLOW}{cli} help encrypt{Colors.RESET})
""")


def show_topic_help(topic: str):
    """Display targeted help and documentation for a specific command."""
    cli = get_cli_name()
    print_banner()
    topic = topic.lower().strip()

    if topic == "encrypt":
        print(f"""
{Colors.BOLD}{Colors.CYAN}COMMAND: encrypt{Colors.RESET}
──────────────────────────────────────────────────────────────────────────────
Encrypts a single file or an entire directory into a secure {Colors.CYAN}.vlt{Colors.RESET} archive.

{Colors.BOLD}SYNTAX:{Colors.RESET}
  {Colors.GREEN}{cli} encrypt <target> [--out <dest>] [--wipe] [--keep]{Colors.RESET}

{Colors.BOLD}ARGUMENTS & FLAGS:{Colors.RESET}
  {Colors.BOLD}target{Colors.RESET}        Path to the file or directory you want to encrypt.
  {Colors.BOLD}--out <dest>{Colors.RESET}  (Optional) Path for the output vault file.
                Default: '<target>.vlt'
  {Colors.BOLD}--wipe{Colors.RESET}        (Optional) Automatically shred and delete original source files.
  {Colors.BOLD}--keep{Colors.RESET}        (Optional) Keep original source files without asking.

{Colors.BOLD}HOW IT WORKS & DELETION POLICY:{Colors.RESET}
  1. Prompts for a master password with confirmation (minimum 8 characters).
  2. If target is a directory, it packages the folder hierarchy into an in-memory tarball.
  3. Uses Argon2id to derive a 256-bit key from your password and a random 16-byte salt.
  4. Encrypts the payload in 64 KiB chunks using AES-256-GCM with fresh nonces.
  5. {Colors.BOLD}Original Cleanup:{Colors.RESET}
     • If {Colors.CYAN}--wipe{Colors.RESET} is specified, original files are overwritten with random data
       and securely shredded immediately.
     • If {Colors.CYAN}--keep{Colors.RESET} is specified, original files are kept without prompting.
     • If neither flag is passed, you will be prompted: {Colors.YELLOW}Delete original? [y/N]{Colors.RESET}

{Colors.BOLD}EXAMPLES:{Colors.RESET}
  {cli} encrypt project_files/
  {cli} encrypt project_files/ --wipe
  {cli} encrypt database.sql --out db_backup.vlt --keep
""")

    elif topic == "decrypt":
        print(f"""
{Colors.BOLD}{Colors.CYAN}COMMAND: decrypt{Colors.RESET}
──────────────────────────────────────────────────────────────────────────────
Decrypts a {Colors.CYAN}.vlt{Colors.RESET} vault file and restores the original file or folder structure.

{Colors.BOLD}SYNTAX:{Colors.RESET}
  {Colors.GREEN}{cli} decrypt <vault_file> [--out <dest>]{Colors.RESET}

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
  {Colors.BOLD}vault_file{Colors.RESET}    Path to the encrypted .vlt file.
  {Colors.BOLD}--out <dest>{Colors.RESET}  (Optional) Destination directory or file path.
                Default: Automatically restores the original filename and timestamps!

{Colors.BOLD}HOW IT WORKS:{Colors.RESET}
  1. Reads header to retrieve salt, Argon2id parameters, and encrypted metadata.
  2. Prompts for the password and derives the AES-256 key.
  3. Decrypts and authenticates metadata (original filename, file type, timestamps).
  4. Restores single files with their original name and timestamp without needing --out.
  5. If folder, restores directory structure and hierarchy into the original folder name.
  6. Verifies each chunk's GCM authentication tag during streaming decryption.

{Colors.BOLD}EXAMPLES:{Colors.RESET}
  # Restores with original filename & timestamp automatically:
  {cli} decrypt backup.vlt

  # Or restore to an explicit destination:
  {cli} decrypt backup.vlt --out /home/user/restored_docs/
""")

    elif topic == "list":
        print(f"""
{Colors.BOLD}{Colors.CYAN}COMMAND: list{Colors.RESET}
──────────────────────────────────────────────────────────────────────────────
Inspects the table of contents of an encrypted folder vault without writing anything to disk.

{Colors.BOLD}SYNTAX:{Colors.RESET}
  {Colors.GREEN}{cli} list <vault_file>{Colors.RESET}

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
  {Colors.BOLD}vault_file{Colors.RESET}    Path to the encrypted .vlt file.

{Colors.BOLD}HOW IT WORKS:{Colors.RESET}
  1. Prompts for your password and decrypts the archive in-memory.
  2. Parses the tar archive structure and displays directory names, file names,
     and uncompressed sizes.
  3. Nothing is written to your disk, preserving privacy.

{Colors.BOLD}EXAMPLE:{Colors.RESET}
  {cli} list confidential_docs.vlt
""")

    elif topic == "verify":
        print(f"""
{Colors.BOLD}{Colors.CYAN}COMMAND: verify{Colors.RESET}
──────────────────────────────────────────────────────────────────────────────
Checks password validity and verifies the cryptographic integrity of every chunk.

{Colors.BOLD}SYNTAX:{Colors.RESET}
  {Colors.GREEN}{cli} verify <vault_file>{Colors.RESET}

{Colors.BOLD}ARGUMENTS:{Colors.RESET}
  {Colors.BOLD}vault_file{Colors.RESET}    Path to the encrypted .vlt file.

{Colors.BOLD}HOW IT WORKS:{Colors.RESET}
  1. Validates the password using Argon2id.
  2. Decrypts every chunk into a dummy buffer, validating each 16-byte GCM tag.
  3. Exits with OK if completely authentic, or raises an error if tampered with.
  4. Instant verification without creating any plaintext files on disk.

{Colors.BOLD}EXAMPLE:{Colors.RESET}
  {cli} verify backup.vlt
""")

    else:
        print(f"{Colors.RED}Unknown topic '{topic}'.{Colors.RESET}\n")
        print(f"Available topics: {Colors.CYAN}encrypt{Colors.RESET}, {Colors.CYAN}decrypt{Colors.RESET}, {Colors.CYAN}list{Colors.RESET}, {Colors.CYAN}verify{Colors.RESET}")
        print(f"Run {Colors.YELLOW}python vault.py help{Colors.RESET} for general usage.")


# ------------------------------------------------------------------
# Dependency check
# ------------------------------------------------------------------
def check_dependencies():
    """Verify external crypto libraries are available."""
    missing = []
    try:
        import argon2.low_level
    except ImportError:
        missing.append("argon2-cffi")
    try:
        import cryptography.hazmat.primitives.ciphers.aead
    except ImportError:
        missing.append("cryptography")

    if missing:
        print(f"\n{Colors.RED}{Colors.BOLD}Error: Missing required Python dependencies:{Colors.RESET} {', '.join(missing)}\n")
        print("To install them, run:")
        print(f"  {Colors.GREEN}pip install {' '.join(missing)}{Colors.RESET}\n")
        print("Or if using a virtual environment:")
        print(f"  {Colors.GREEN}python3 -m venv .venv && source .venv/bin/activate && pip install {' '.join(missing)}{Colors.RESET}\n")
        sys.exit(1)



# ------------------------------------------------------------------
# Key derivation
# ------------------------------------------------------------------
def derive_key(password: str, salt: bytes,
               time_cost: int = ARGON2_TIME,
               memory_cost: int = ARGON2_MEM,
               parallelism: int = ARGON2_PARA) -> bytes:
    """Argon2id — memory-hard KDF, resists GPU/ASIC brute force."""
    try:
        from argon2.low_level import hash_secret_raw, Type
    except ImportError:
        check_dependencies()
        raise

    return hash_secret_raw(
        secret=password.encode("utf-8"),
        salt=salt,
        time_cost=time_cost,
        memory_cost=memory_cost,
        parallelism=parallelism,
        hash_len=KEY_LEN,
        type=Type.ID,
    )


# ------------------------------------------------------------------
# Streaming encryption / decryption (chunked for large files)
# ------------------------------------------------------------------
def encrypt_stream(infile: io.BufferedReader, outfile: io.BufferedWriter,
                   key: bytes) -> int:
    """Encrypt in 64 KiB chunks. Each chunk gets its own nonce.
    Format per chunk: nonce(12) | ct_len(u4) | ciphertext."""
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        check_dependencies()
        raise

    aesgcm = AESGCM(key)
    chunks = 0
    while True:
        chunk = infile.read(CHUNK_SIZE)
        if not chunk:
            break
        nonce = os.urandom(NONCE_LEN)
        ct = aesgcm.encrypt(nonce, chunk, None)
        outfile.write(nonce)
        outfile.write(struct.pack(">I", len(ct)))
        outfile.write(ct)
        chunks += 1
    return chunks


def decrypt_stream(infile: io.BufferedReader, outfile: io.BufferedWriter,
                   key: bytes) -> int:
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        check_dependencies()
        raise

    aesgcm = AESGCM(key)
    chunks = 0
    while True:
        nonce = infile.read(NONCE_LEN)
        if not nonce:
            break
        if len(nonce) < NONCE_LEN:
            raise ValueError("Corrupt vault: truncated nonce.")
        len_bytes = infile.read(4)
        if len(len_bytes) < 4:
            raise ValueError("Corrupt vault: truncated length.")
        ct_len = struct.unpack(">I", len_bytes)[0]
        ct = infile.read(ct_len)
        if len(ct) < ct_len:
            raise ValueError("Corrupt vault: truncated ciphertext.")
        try:
            plaintext = aesgcm.decrypt(nonce, ct, None)
        except Exception as e:
            raise ValueError(
                "Authentication failed — wrong password or tampered vault."
            ) from e
        outfile.write(plaintext)
        chunks += 1
    return chunks


# ------------------------------------------------------------------
# Pack folder -> tar bytes -> encrypted vault
# ------------------------------------------------------------------
def pack_folder(folder: Path) -> bytes:
    """Tar the folder in memory (preserves structure)."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        tar.add(folder, arcname=folder.name)
    buf.seek(0)
    return buf


# ------------------------------------------------------------------
# Secure File Shredding & Deletion
# ------------------------------------------------------------------
def shred_file(path: Path, passes: int = 1):
    """Overwrites a file with random data before unlinking to prevent recovery."""
    try:
        if path.is_symlink():
            path.unlink()
            return
        size = path.stat().st_size
        if size > 0:
            with open(path, "ba+", buffering=0) as f:
                for _ in range(passes):
                    f.seek(0)
                    remaining = size
                    while remaining > 0:
                        to_write = min(remaining, 64 * 1024)
                        f.write(os.urandom(to_write))
                        remaining -= to_write
                    f.flush()
                    os.fsync(f.fileno())
        path.unlink()
    except Exception:
        if path.exists():
            path.unlink(missing_ok=True)


def secure_wipe(target: Path):
    """Securely overwrite and remove a file or directory tree."""
    if not target.exists() and not target.is_symlink():
        return

    if target.is_file() or target.is_symlink():
        shred_file(target)
        print(f"{Colors.GREEN}✔ Securely shredded original file: {target}{Colors.RESET}")
    elif target.is_dir():
        # Shred all files recursively from deepest first
        for item in sorted(target.rglob("*"), key=lambda p: len(str(p)), reverse=True):
            if item.is_file() or item.is_symlink():
                shred_file(item)
            elif item.is_dir():
                try:
                    item.rmdir()
                except OSError:
                    pass
        try:
            if target.exists():
                shutil.rmtree(target)
        except Exception:
            pass
        print(f"{Colors.GREEN}✔ Securely shredded original folder: {target}{Colors.RESET}")


# ------------------------------------------------------------------
# Password Input (Interactive TTY, Stdin Pipe, or Environment)
# ------------------------------------------------------------------
def prompt_password(prompt: str = "Password: ") -> str:
    """Get password from VAULT_PASSWORD env var, stdin pipe, or secure getpass."""
    env_pw = os.environ.get("VAULT_PASSWORD")
    if env_pw is not None:
        return env_pw
    if not sys.stdin.isatty():
        return sys.stdin.readline().rstrip("\r\n")
    return getpass.getpass(prompt)


# ------------------------------------------------------------------
# Public commands
# ------------------------------------------------------------------
def cmd_encrypt(target: str, out_path: str, wipe: bool = False, keep: bool = False):
    check_dependencies()
    src = Path(target)
    if not src.exists():
        sys.exit(f"{Colors.RED}Error: {src} does not exist.{Colors.RESET}")

    out = Path(out_path)
    if out.resolve() == src.resolve():
        sys.exit(f"{Colors.RED}Error: Output vault path cannot be identical to target source.{Colors.RESET}")

    password = prompt_password("Password: ")
    if os.environ.get("VAULT_PASSWORD") or not sys.stdin.isatty():
        confirm = password
    else:
        confirm = prompt_password("Confirm : ")
    if password != confirm:
        sys.exit(f"{Colors.RED}Passwords do not match.{Colors.RESET}")
    if len(password) < 8:
        sys.exit(f"{Colors.RED}Password must be at least 8 characters.{Colors.RESET}")

    salt = os.urandom(SALT_LEN)

    print(f"{Colors.CYAN}Deriving key (Argon2id)... this takes a moment by design.{Colors.RESET}")
    t0 = time.time()
    key = derive_key(password, salt)
    print(f"  done in {time.time() - t0:.2f}s")

    # Encrypt metadata block (V2)
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    aesgcm = AESGCM(key)

    stat = src.stat()
    meta = {
        "name": src.name,
        "is_dir": src.is_dir(),
        "size": stat.st_size if src.is_file() else 0,
        "mtime": stat.st_mtime,
    }
    meta_bytes = json.dumps(meta).encode("utf-8")
    meta_nonce = os.urandom(NONCE_LEN)
    meta_ct = aesgcm.encrypt(meta_nonce, meta_bytes, b"VAULT_META")
    meta_len = len(meta_ct)

    with open(out, "wb") as fout:
        # Reserve header + metadata space: HEADER_SIZE_V2 + NONCE_LEN + meta_len
        total_header_size = HEADER_SIZE_V2 + NONCE_LEN + meta_len
        fout.write(b"\x00" * total_header_size)

        if src.is_file():
            with open(src, "rb") as fin:
                chunks = encrypt_stream(fin, fout, key)
        else:
            print(f"Packing folder: {src}")
            buf = pack_folder(src)
            chunks = encrypt_stream(buf, fout, key)

        # Write header and encrypted metadata at offset 0
        fout.seek(0)
        fout.write(struct.pack(
            HEADER_FMT_V2, MAGIC_V2, salt,
            ARGON2_TIME, ARGON2_MEM, ARGON2_PARA, chunks, meta_len
        ))
        fout.write(meta_nonce)
        fout.write(meta_ct)

    size = out.stat().st_size
    size_label = "directory" if meta["is_dir"] else f"{meta['size']:,} bytes"
    print(f"\n{Colors.GREEN}✔ Encrypted -> {out}{Colors.RESET}  ({size:,} bytes, {chunks} chunks)")
    print(f"  Original: {Colors.CYAN}{meta['name']}{Colors.RESET} ({size_label})")
    print(f"{Colors.YELLOW}Important: Keep your password. There is no recovery without it.{Colors.RESET}")

    # Secure deletion handling
    if wipe:
        print(f"\n{Colors.CYAN}Shredding original source (--wipe enabled)...{Colors.RESET}")
        secure_wipe(src)
    elif keep:
        print(f"\nKept original source (--keep enabled).")
    else:
        try:
            ans = input(f"\n{Colors.YELLOW}Delete original '{src}'? [y/N]: {Colors.RESET}").strip().lower()
            if ans in ("y", "yes"):
                secure_wipe(src)
            else:
                print(f"Kept original '{src}'.")
        except (KeyboardInterrupt, EOFError):
            print(f"\nKept original '{src}'.")


def _read_header(fin) -> dict:
    magic = fin.read(8)
    if len(magic) < 8:
        sys.exit(f"{Colors.RED}Error: Not a vault file (too small).{Colors.RESET}")

    if magic == MAGIC_V2:
        rem_len = HEADER_SIZE_V2 - 8
        raw = fin.read(rem_len)
        if len(raw) < rem_len:
            sys.exit(f"{Colors.RED}Error: Incomplete V2 vault header.{Colors.RESET}")
        salt, t, m, p, chunks, meta_len = struct.unpack(">16sIIIQI", raw)
        meta_nonce = fin.read(NONCE_LEN)
        if len(meta_nonce) < NONCE_LEN:
            sys.exit(f"{Colors.RED}Error: Incomplete metadata nonce in vault.{Colors.RESET}")
        meta_ct = fin.read(meta_len)
        if len(meta_ct) < meta_len:
            sys.exit(f"{Colors.RED}Error: Incomplete metadata block in vault.{Colors.RESET}")
        return {
            "version": 2,
            "salt": salt,
            "time": t,
            "mem": m,
            "para": p,
            "chunks": chunks,
            "meta_nonce": meta_nonce,
            "meta_ct": meta_ct,
        }
    elif magic == MAGIC_V1:
        rem_len = HEADER_SIZE_V1 - 8
        raw = fin.read(rem_len)
        if len(raw) < rem_len:
            sys.exit(f"{Colors.RED}Error: Incomplete V1 vault header.{Colors.RESET}")
        salt, t, m, p, chunks = struct.unpack(">16sIIIQ", raw)
        return {
            "version": 1,
            "salt": salt,
            "time": t,
            "mem": m,
            "para": p,
            "chunks": chunks,
            "meta_nonce": None,
            "meta_ct": None,
        }
    else:
        sys.exit(f"{Colors.RED}Error: Not a valid vault file (unrecognized format identifier).{Colors.RESET}")


def cmd_decrypt(vault_path: str, out_path: str = None):
    check_dependencies()
    vp = Path(vault_path)
    if not vp.exists():
        sys.exit(f"{Colors.RED}Error: {vp} does not exist.{Colors.RESET}")

    password = prompt_password("Password: ")

    with open(vp, "rb") as fin:
        hdr = _read_header(fin)
        print(f"Vault [V{hdr['version']}]: {hdr['chunks']} chunks, Argon2id "
              f"(t={hdr['time']}, m={hdr['mem']} KiB, p={hdr['para']})")
        print(f"{Colors.CYAN}Deriving key...{Colors.RESET}")
        key = derive_key(password, hdr["salt"],
                         hdr["time"], hdr["mem"], hdr["para"])

        # Decrypt metadata block if V2
        meta = None
        if hdr["version"] == 2:
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                aesgcm = AESGCM(key)
                meta_raw = aesgcm.decrypt(hdr["meta_nonce"], hdr["meta_ct"], b"VAULT_META")
                meta = json.loads(meta_raw.decode("utf-8"))
            except Exception as e:
                sys.exit(f"{Colors.RED}Authentication failed — wrong password or tampered vault metadata.{Colors.RESET}")

        # Decrypt chunk stream to buffer
        buf = io.BytesIO()
        try:
            decrypt_stream(fin, buf, key)
        except ValueError as e:
            sys.exit(f"{Colors.RED}Decryption failed: {e}{Colors.RESET}")

    buf.seek(0)

    # Determine whether payload is a directory or single file
    if meta and "is_dir" in meta:
        is_tar = meta["is_dir"]
    else:
        is_tar = False
        try:
            with tarfile.open(fileobj=buf, mode="r"):
                is_tar = True
        except tarfile.TarError:
            is_tar = False
    buf.seek(0)

    if is_tar:
        with tarfile.open(fileobj=buf, mode="r") as tar:
            members = tar.getmembers()
            if out_path:
                out = Path(out_path)
                out.mkdir(parents=True, exist_ok=True)
                extract_target = out
                display_dest = str(out)
            else:
                extract_target = Path(".")
                display_dest = meta["name"] if (meta and meta.get("name")) else "restored"

            print(f"Extracting {len(members)} items...")
            try:
                tar.extractall(path=extract_target, filter="data")
            except TypeError:
                tar.extractall(path=extract_target)

            if meta and "mtime" in meta:
                target_dir = Path(display_dest)
                if target_dir.exists():
                    try:
                        os.utime(target_dir, (meta["mtime"], meta["mtime"]))
                    except OSError:
                        pass

        print(f"{Colors.GREEN}✔ Restored folder -> {display_dest}/{Colors.RESET} (hierarchy preserved)")
        return

    # Single file
    if out_path:
        out = Path(out_path)
        if out.is_dir():
            target_name = meta["name"] if (meta and meta.get("name")) else (vp.stem.replace(".vlt", "") or "restored")
            out = out / target_name
    elif meta and meta.get("name"):
        out = Path(meta["name"])
    else:
        out = Path(vp.stem.replace(".vlt", "") or "restored")

    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "wb") as f:
        f.write(buf.getvalue())

    # Restore modification timestamp if recorded
    mtime_notice = ""
    if meta and "mtime" in meta:
        try:
            os.utime(out, (meta["mtime"], meta["mtime"]))
            dt = datetime.datetime.fromtimestamp(meta["mtime"]).strftime("%Y-%m-%d %H:%M:%S")
            mtime_notice = f" (timestamp: {dt})"
        except OSError:
            pass

    print(f"{Colors.GREEN}✔ Restored file -> {out}{Colors.RESET}{mtime_notice}")


def cmd_list(vault_path: str):
    check_dependencies()
    vp = Path(vault_path)
    if not vp.exists():
        sys.exit(f"{Colors.RED}Error: {vp} does not exist.{Colors.RESET}")

    password = prompt_password("Password: ")
    with open(vp, "rb") as fin:
        hdr = _read_header(fin)
        key = derive_key(password, hdr["salt"],
                         hdr["time"], hdr["mem"], hdr["para"])

        # Decrypt metadata if V2
        meta = None
        if hdr["version"] == 2:
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                aesgcm = AESGCM(key)
                meta_raw = aesgcm.decrypt(hdr["meta_nonce"], hdr["meta_ct"], b"VAULT_META")
                meta = json.loads(meta_raw.decode("utf-8"))
            except Exception as e:
                sys.exit(f"{Colors.RED}Authentication failed: wrong password or tampered metadata.{Colors.RESET}")

        buf = io.BytesIO()
        try:
            decrypt_stream(fin, buf, key)
        except ValueError as e:
            sys.exit(f"{Colors.RED}Failed: {e}{Colors.RESET}")

    buf.seek(0)
    print(f"\n{Colors.BOLD}Vault Archive Details:{Colors.RESET}")
    print(f"  Vault File:    {Colors.CYAN}{vp.name}{Colors.RESET} (Format: V{hdr['version']})")
    if meta:
        dt = datetime.datetime.fromtimestamp(meta["mtime"]).strftime("%Y-%m-%d %H:%M:%S") if "mtime" in meta else "N/A"
        print(f"  Target Name:   {Colors.BOLD}{meta.get('name')}{Colors.RESET}")
        print(f"  Target Type:   {'Directory' if meta.get('is_dir') else 'Single File'}")
        if not meta.get("is_dir"):
            print(f"  Original Size: {meta.get('size', 0):,} bytes")
        print(f"  Modified:      {dt}")

    if (meta and meta.get("is_dir")) or (meta is None):
        try:
            with tarfile.open(fileobj=buf, mode="r") as tar:
                print(f"\n{Colors.BOLD}Directory Contents:{Colors.RESET}")
                for m in tar.getmembers():
                    kind = f"{Colors.CYAN}DIR {Colors.RESET}" if m.isdir() else f"{Colors.GREEN}FILE{Colors.RESET}"
                    print(f"  [{kind}] {m.name:<40} ({m.size:,} bytes)")
        except tarfile.TarError:
            if not meta:
                print(f"{Colors.YELLOW}Vault contains a single encrypted file (not a folder).{Colors.RESET}")


def cmd_verify(vault_path: str):
    check_dependencies()
    vp = Path(vault_path)
    if not vp.exists():
        sys.exit(f"{Colors.RED}Error: {vp} does not exist.{Colors.RESET}")

    password = prompt_password("Password: ")
    with open(vp, "rb") as fin:
        hdr = _read_header(fin)
        key = derive_key(password, hdr["salt"],
                         hdr["time"], hdr["mem"], hdr["para"])

        # Verify metadata block if V2
        if hdr["version"] == 2:
            try:
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                aesgcm = AESGCM(key)
                aesgcm.decrypt(hdr["meta_nonce"], hdr["meta_ct"], b"VAULT_META")
            except Exception as e:
                sys.exit(f"{Colors.RED}INTEGRITY FAIL: Metadata block corrupted or wrong password.{Colors.RESET}")

        try:
            n = decrypt_stream(fin, io.BytesIO(), key)
        except ValueError as e:
            sys.exit(f"{Colors.RED}INTEGRITY FAIL: {e}{Colors.RESET}")

    meta_msg = "metadata and " if hdr["version"] == 2 else ""
    print(f"{Colors.GREEN}✔ OK{Colors.RESET} — {meta_msg}{n} chunks verified. Vault is authentic and password is correct.")


# ------------------------------------------------------------------
# Custom Argument Parser
# ------------------------------------------------------------------
class VaultArgumentParser(argparse.ArgumentParser):
    """Custom parser to format help with the tool banner and styling."""
    def format_help(self):
        show_general_help()
        return ""


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------
def main():
    # If called with no arguments, display the full interactive banner and help
    if len(sys.argv) == 1:
        show_general_help()
        sys.exit(0)

    p = VaultArgumentParser(
        description=f"{TOOL_NAME} — Encrypted Archive CLI",
        add_help=True
    )
    sub = p.add_subparsers(dest="cmd")

    # encrypt
    e = sub.add_parser("encrypt", help="Encrypt a file or folder")
    e.add_argument("target", help="File or folder path to encrypt")
    e.add_argument("--out", default=None, help="Output .vlt destination")
    e.add_argument("--wipe", action="store_true", help="Automatically shred original files after encryption")
    e.add_argument("--keep", action="store_true", help="Keep original files without prompting")

    # decrypt
    d = sub.add_parser("decrypt", help="Decrypt a vault")
    d.add_argument("vault", help="Path to .vlt vault file")
    d.add_argument("--out", default=None, help="Output destination folder or file (default: restores original name)")

    # list
    l = sub.add_parser("list", help="List vault contents without extracting")
    l.add_argument("vault", help="Path to .vlt vault file")

    # verify
    v = sub.add_parser("verify", help="Verify integrity tags and password")
    v.add_argument("vault", help="Path to .vlt vault file")

    # help
    h = sub.add_parser("help", help="Show detailed documentation and examples")
    h.add_argument("topic", nargs="?", default=None, help="Command to show detailed help for (encrypt, decrypt, list, verify)")

    args = p.parse_args()

    if args.cmd == "encrypt":
        out = args.out or (args.target.rstrip("/\\") + ".vlt")
        cmd_encrypt(args.target, out, wipe=args.wipe, keep=args.keep)
    elif args.cmd == "decrypt":
        cmd_decrypt(args.vault, args.out)
    elif args.cmd == "list":
        cmd_list(args.vault)
    elif args.cmd == "verify":
        cmd_verify(args.vault)
    elif args.cmd == "help":
        if args.topic:
            show_topic_help(args.topic)
        else:
            show_general_help()
    else:
        show_general_help()


if __name__ == "__main__":
    main()
