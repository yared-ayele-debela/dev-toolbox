# 🔒 Personal Vault — User Guide & Documentation

A high-security CLI utility to encrypt files and directories into tamper-resistant `.vlt` archives using **AES-256-GCM** authenticated encryption and **Argon2id** memory-hard key derivation.

---

## 📋 Table of Contents
1. [Installation & Setup](#installation--setup)
2. [Built-in Help & Interactive Display](#built-in-help--interactive-display)
3. [Command Reference](#command-reference)
   - [1. Encrypting Files & Folders (`encrypt`)](#1-encrypting-files--folders-encrypt)
   - [2. Inspecting Contents (`list`)](#2-inspecting-contents-list)
   - [3. Decrypting Archives (`decrypt`)](#3-decrypting-archives-decrypt)
   - [4. Verifying Integrity (`verify`)](#4-verifying-integrity-verify)
4. [Cryptographic Specifications](#cryptographic-specifications)
5. [Security Best Practices](#security-best-practices)

---

## Installation & Setup

### 1. One-Click Global Install (Recommended)
Run the install script inside the project directory:
```bash
./install.sh
```
This automatically links the tool to `~/.local/bin/vault` so you can type `vault` from any terminal directory.

### 2. Manual Installation
```bash
pip install -r requirements.txt
ln -sf "$(pwd)/vault.py" ~/.local/bin/vault
chmod +x ~/.local/bin/vault
```

---

## Built-in Help & Interactive Display

You can run `vault` directly anywhere in your terminal:

```bash
# Display tool banner, description, commands, and quick examples
vault

# Standard help flag
vault --help

# Detailed guide for a specific command
vault help encrypt
vault help decrypt
vault help list
vault help verify
```

---

## Command Reference

### 1. Encrypting Files & Folders (`encrypt`)
Packs and encrypts the target path into a `.vlt` vault file.

```bash
python vault.py encrypt <target> [--out <dest>] [--wipe] [--keep]
```

#### Secure Deletion & Shredding Policy:
* **Interactive Prompt (Default)**: After successfully writing and verifying the `.vlt` file, the tool asks:
  ```text
  Delete original '<target>'? [y/N]:
  ```
  Answering `y` securely shreds the files.
* **`--wipe` flag**: Automatically overwrites all original files with cryptographic random data (`os.urandom`) and unlinks them immediately without asking.
* **`--keep` flag**: Automatically keeps original unencrypted files without asking (useful for non-interactive backup scripts).

#### Examples:
* **Encrypt a directory (asks to delete original):**
  ```bash
  python vault.py encrypt /home/user/my_secret_project/
  # Creates my_secret_project.vlt and prompts to delete original
  ```

* **Encrypt and automatically shred the unencrypted original:**
  ```bash
  python vault.py encrypt confidential_folder/ --wipe
  ```

* **Encrypt a single file with custom output filename, keeping the original:**
  ```bash
  python vault.py encrypt database.sql --out 2026_db_backup.vlt --keep
  ```

---

### 2. Inspecting Contents (`list`)
Inspects the metadata and internal directory contents of an encrypted vault **without** extracting them to disk.

```bash
python vault.py list <vault_file>
```

#### Example:
```bash
python vault.py list project_backup.vlt
```
*Output preview:*
```text
Vault Archive Details:
  Vault File:    project_backup.vlt (Format: V2)
  Target Name:   my_project
  Target Type:   Directory
  Modified:      2026-09-12 01:30:00

Directory Contents:
  [DIR ] my_project/                             (0 bytes)
  [FILE] my_project/config.json                  (1,248 bytes)
  [FILE] my_project/passwords.kdbx               (64,520 bytes)
```

---

### 3. Decrypting Archives (`decrypt`)
Restores an encrypted `.vlt` archive back to its original file or directory structure.

```bash
python vault.py decrypt <vault_file> [--out <dest>]
```

#### 🌟 Smart Restoration (No `--out` required):
The vault stores an encrypted metadata block containing the original filename, file type, and modification timestamp:
* When decrypting without `--out`, **it automatically restores the exact original file or folder name and timestamp**.
* You only need `--out` if you want to override the destination.

#### Examples:
* **Smart restore (restores original name & timestamp automatically):**
  ```bash
  python vault.py decrypt secret_report.pdf.vlt
  # ✔ Restored file -> secret_report.pdf (timestamp: 2026-09-12 01:30:00)
  ```

* **Smart restore for a folder vault:**
  ```bash
  python vault.py decrypt project_backup.vlt
  # ✔ Restored folder -> my_project/ (hierarchy preserved)
  ```

* **Restore to a custom destination:**
  ```bash
  python vault.py decrypt project_backup.vlt --out /home/user/workspace/
  ```

---

### 4. Verifying Integrity (`verify`)
Validates that the password is correct and that no bytes in the archive have been altered or corrupted.

```bash
python vault.py verify <vault_file>
```

#### Example:
```bash
python vault.py verify project_backup.vlt
# ✔ OK — 32 chunks verified. Vault is authentic and password is correct.
```

---

## Cryptographic Specifications

| Component | Standard / Algorithm | Parameters |
| :--- | :--- | :--- |
| **Cipher** | AES-256-GCM (AEAD) | 256-bit key, 12-byte random nonce per chunk, 16-byte auth tag |
| **KDF** | Argon2id | Memory: 64 MiB, Time: 3 passes, Parallelism: 4 threads |
| **Salt** | CSPRNG (`os.urandom`) | 16 bytes |
| **Chunking** | Stream Processing | 64 KiB chunks |
| **Integrity** | End-to-End AEAD | Each chunk is authenticated independently |

---

## Security Best Practices
1. **Password Length**: Use a passphrase of at least 12–16 characters (or generated by a password manager). Minimum enforced is 8 characters.
2. **No Backdoor / No Recovery**: There is deliberately no master password or backdoor. If you lose your password, the data cannot be recovered.
3. **Tamper Detection**: Any modification to the encrypted file (even 1 bit) will cause decryption and verification to abort immediately.
