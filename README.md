# MAQAM AI — Portfolio publishing setup

This public repository is being prepared to host the **MAQAM AI computational-musicology research prototype**.

## Finish the one-file import

1. Download the already prepared `MAQAM_GITHUB_READY_2026-11-11.zip` file from the ChatGPT conversation.
2. In this repository, click **Add file → Upload files**. Upload that ZIP *without unzipping it*, directly to the root of the `main` branch; then click **Commit changes**.
3. GitHub Actions **Import MAQAM portfolio** verifies the pinned ZIP checksum, safely extracts all 147 files, commits the source into this repository, and removes the ZIP.
4. Refresh this page after the import workflow finishes. The full project's professional README replaces these instructions.
5. For a professional CV URL, go to **Settings → General → Repository name** and rename `Proj1` to `maqam-ai`. GitHub automatically redirects the old repository URL.

**Do not upload transcripts, personal records, secret keys or application essays.** The pinned ZIP was prepared as a curated technical portfolio.

**Evidence boundary:** MAQAM is a research software prototype with formal algorithms and constructed-fixture tests; independent real-world musical alignment accuracy is not established.
