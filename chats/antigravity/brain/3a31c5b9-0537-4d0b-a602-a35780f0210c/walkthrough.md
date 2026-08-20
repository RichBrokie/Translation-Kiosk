# Data Cleaning Walkthrough

The cleanup script has successfully processed the dataset and resolved the anomalies. The total number of rows went from 1,192 to 1,186, meaning 6 additional exact duplicates were identified and removed after formatting the names correctly.

Here is a summary of the improvements:

### 1. Vendor Name Standardization
- **Casing Issues Fixed:** The 113 names that were entirely lowercase (e.g., `samosa station`) and 47 names that were entirely uppercase (e.g., `HAB`) were converted into proper Title Case (`Samosa Station`, `Hab`).
- **Whitespace Removed:** Multiple trailing, leading, and consecutive spaces were cleaned up. For example, `Care Pakistan  Plus Bazzazi` became `Care Pakistan Plus Bazzazi`.

### 2. Misplaced Data Corrections
- **Emails Fixed:** 5 entries where the Vendor Name was actually an email address (e.g., `MQ.officialmgmt@gmail.com`) were moved to the `Email` column, and their Vendor Name was set to "Unknown Vendor".
- **Phone Numbers Fixed:** 2 entries where the Vendor Name was entirely numerical (e.g., `03328508399`) were safely moved to the `Contact Number` column.

### 3. Contact Number Standardization
- **Letters Removed:** Phone numbers mixed with text (e.g., `Phone: +92 21 11 11 1LINK (15465)`, `Cell no. 03008494702`) had the letters stripped away to leave only the digits. 
- **Text Relocated:** Entries in the phone number column containing no numbers (e.g., `Cold`) were appended to the `Notes` column instead.
- **Uniform Format:** All standard Pakistani cell numbers were normalized to the `03XX XXXXXXX` format. For example:
  - `923344000000` ➔ `0334 4000000`
  - `3212760038` ➔ `0321 2760038`

You can verify the cleaned data by opening the updated [Compiled_Vendors.xlsx](file:///home/ahmad/Downloads/Art%20Society/Compiled_Vendors.xlsx).
