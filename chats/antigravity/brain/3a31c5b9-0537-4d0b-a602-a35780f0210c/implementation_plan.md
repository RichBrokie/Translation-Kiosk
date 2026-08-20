# Clean and Standardize Vendor Data

The `Compiled_Vendors.xlsx` file currently has 1,192 entries. After running an initial analysis, I have identified several anomalies and inconsistencies that need to be addressed to make the data clean and professional.

## User Review Required

Please review the proposed cleaning rules below. If you want me to handle any specific anomalies differently (for example, how to format phone numbers), let me know before I execute the script.

## Open Questions

- **Phone Number Format:** I propose formatting all Pakistani mobile numbers to the standard `03XX XXXXXXX` format (e.g., `0300 1234567`). Landlines will be cleaned to `042 XXXXXXX`. Does this format work for you, or do you prefer the international format (`+92 3XX...`)?
- **Unknown Names:** If a row only has a phone number or email but no vendor name, I plan to set the Vendor Name to "Unknown Vendor". Is this acceptable, or should I drop those rows entirely?

## Proposed Changes

I will write a Python script that reads the Excel file, applies the following rules, and rewrites the clean data back to the formatted Excel file:

### 1. Name Formatting & Cleanup
- Convert all `Vendor Name` and `Contact Person` entries to **Title Case** to fix the 113 lowercase and 47 ALL-CAPS names.
- Replace multiple consecutive spaces with a single space.
- Strip leading and trailing whitespace from all text columns.

### 2. Misplaced Data
- **Emails as Names:** If a `Vendor Name` contains an `@` (e.g., `MQ.officialmgmt@gmail.com`), the script will move it to the `Email` column and set the Vendor Name to "Unknown Vendor" (or try to extract a name from the email prefix).
- **Phone Numbers as Names:** If a `Vendor Name` consists entirely of numbers (e.g., `03328508399`), it will be moved to the `Contact Number` column.

### 3. Contact Number Standardization
- **Extracting Numbers:** Remove unnecessary text from phone numbers (e.g., "Phone: ", "Cell no.", "Ext.").
- **Handling Text-Only Contacts:** If the Contact Number field contains only letters (e.g., "Cold"), it will be moved to the `Notes` column since it isn't a valid phone number.
- **Formatting:** Standardize all 10-digit (without 0), 11-digit (with 0), and 12-digit (with 92) mobile numbers to a clean `03XX XXXXXXX` format.

## Verification Plan

### Automated Tests
- The script will output a before/after summary of the anomalies (e.g., checking that the number of all-lowercase names is now 0).

### Manual Verification
- I will verify the changes and present you with a few random "Before vs. After" rows in a Walkthrough artifact to ensure the anomalies were successfully resolved.
