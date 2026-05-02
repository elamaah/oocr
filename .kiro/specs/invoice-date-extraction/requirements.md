# Requirements Document - Complete Invoice Extraction Engine

## Introduction

This feature provides a comprehensive rule-based invoice extraction engine for OCR-extracted invoice text. The system processes bilingual (Arabic and English) invoice text from PaddleOCR and extracts multiple fields including dates, times, total amounts, items with quantities and prices, and invoice categories. The engine uses a candidate-based architecture where multiple candidates are generated for each field, scored based on context and position, and the best candidate is selected with a confidence score.

## Glossary

- **Invoice_Extractor**: The complete system responsible for extracting all invoice fields from OCR text
- **OCR_Text**: Raw text extracted from invoice images using PaddleOCR
- **Candidate**: A potential value for any field (date, time, total, item) with an associated score
- **Scoring_Engine**: The component that calculates confidence scores for candidates based on multiple factors
- **Context_Keyword**: A keyword that indicates proximity to a specific field (e.g., "date", "total", "تاريخ", "الإجمالي")
- **Confidence_Score**: A numerical value (0.0 to 1.0) indicating the likelihood that an extracted value is correct
- **Normalized_Text**: Text after converting Arabic numerals to English, fixing OCR errors, and applying lowercase
- **Valid_Date**: A date string that can be successfully parsed into a datetime object
- **Valid_Time**: A time string that can be successfully parsed into a time object
- **Arabic_Numeral**: Arabic-Indic digits (٠١٢٣٤٥٦٧٨٩)
- **English_Numeral**: Western Arabic digits (0123456789)
- **Date_Format**: A specific pattern for representing dates (e.g., DD/MM/YYYY, YYYY-MM-DD)
- **Time_Format**: A specific pattern for representing times (e.g., HH:MM, HH:MM AM/PM)
- **Total_Amount**: The final total amount on an invoice (not subtotal, tax, or discount)
- **Item**: A structured object containing item name, quantity, and price
- **Category**: The classification of an invoice (restaurant, supermarket, pharmacy, etc.)
- **Line**: A single line of text from the invoice
- **Keyword_Proximity**: The distance in characters between a candidate and its nearest context keyword
- **Document_Position**: The location of a candidate in the document (top, middle, bottom)

## Requirements

### Requirement 1: Text Preprocessing and Normalization

**User Story:** As a developer, I want to preprocess and normalize OCR text before extraction, so that patterns can be consistently matched regardless of numeral system, case, or OCR errors.

#### Acceptance Criteria

1. WHEN OCR_Text contains Arabic_Numerals, THE Invoice_Extractor SHALL convert them to English_Numerals
2. WHEN OCR_Text contains uppercase English letters, THE Invoice_Extractor SHALL convert them to lowercase
3. WHEN OCR_Text contains common OCR errors (O→0, I/l→1 in numeric context), THE Invoice_Extractor SHALL correct them
4. THE Invoice_Extractor SHALL remove noise and special characters while preserving meaningful punctuation (periods, commas, colons)
5. THE Invoice_Extractor SHALL split the text into Lines for line-based extraction
6. FOR ALL valid OCR_Text inputs, normalizing twice SHALL produce the same result as normalizing once (idempotence property)
7. THE Invoice_Extractor SHALL handle mixed Arabic and English text without corruption

### Requirement 2: Date Extraction with Candidate Scoring

**User Story:** As a developer, I want to extract invoice dates using a candidate-based approach with scoring, so that I can reliably identify the correct invoice date even when multiple dates are present.

#### Acceptance Criteria

1. WHEN Normalized_Text contains dates in format DD/MM/YYYY, THE Invoice_Extractor SHALL extract them as Candidates
2. WHEN Normalized_Text contains dates in format DD-MM-YYYY, THE Invoice_Extractor SHALL extract them as Candidates
3. WHEN Normalized_Text contains dates in format YYYY/MM/DD, THE Invoice_Extractor SHALL extract them as Candidates
4. WHEN Normalized_Text contains dates in format YYYY-MM-DD, THE Invoice_Extractor SHALL extract them as Candidates
5. WHEN Normalized_Text contains dates in format "DD Month YYYY" (e.g., "12 May 2024"), THE Invoice_Extractor SHALL extract them as Candidates
6. WHEN Normalized_Text contains dates in Arabic format "DD Arabic_Month YYYY" (e.g., "12 مايو 2024"), THE Invoice_Extractor SHALL extract them as Candidates
7. WHEN Normalized_Text contains dates with short year format (e.g., "12/05/24"), THE Invoice_Extractor SHALL extract them as Candidates
8. THE Invoice_Extractor SHALL reject expiry dates if detected through keywords ["expiry", "exp", "انتهاء", "صلاحية"]
9. THE Invoice_Extractor SHALL score each date Candidate based on Keyword_Proximity to ["date", "invoice date", "issued", "تاريخ", "تاريخ الفاتورة"]
10. THE Invoice_Extractor SHALL score each date Candidate based on Document_Position (prefer top of document)
11. THE Invoice_Extractor SHALL select the date Candidate with the highest score
12. FOR ALL valid date strings, extracting candidates then scoring SHALL preserve at least one valid candidate (completeness property)

### Requirement 3: Time Extraction with Candidate Scoring

**User Story:** As a developer, I want to extract invoice times using a candidate-based approach with scoring, so that I can identify the transaction time when present.

#### Acceptance Criteria

1. WHEN Normalized_Text contains times in 24-hour format HH:MM (e.g., "10:30", "22:15"), THE Invoice_Extractor SHALL extract them as Candidates
2. WHEN Normalized_Text contains times in 12-hour format HH:MM AM/PM (e.g., "10:30 AM", "10:30 PM"), THE Invoice_Extractor SHALL extract them as Candidates
3. WHEN Normalized_Text contains times in Arabic 12-hour format HH:MM ص/م (e.g., "10:30 صباحاً", "10:30 مساءً"), THE Invoice_Extractor SHALL extract them as Candidates
4. THE Invoice_Extractor SHALL score each time Candidate based on Keyword_Proximity to ["time", "الوقت"]
5. THE Invoice_Extractor SHALL score each time Candidate based on proximity to the extracted date
6. THE Invoice_Extractor SHALL score each time Candidate based on Document_Position (prefer top of document)
7. THE Invoice_Extractor SHALL select the time Candidate with the highest score
8. WHEN no valid time is found, THE Invoice_Extractor SHALL return None with Confidence_Score 0.0

### Requirement 4: Total Amount Extraction with Candidate Scoring

**User Story:** As a developer, I want to extract the final total amount from invoices using a candidate-based approach with scoring, so that I can identify the correct total even when multiple amounts are present.

#### Acceptance Criteria

1. WHEN Normalized_Text contains numeric values with optional currency symbols, THE Invoice_Extractor SHALL extract them as amount Candidates
2. THE Invoice_Extractor SHALL handle amount formats: "150.50", "150,50", "١٥٠.٥٠", "150", "150.5"
3. THE Invoice_Extractor SHALL score amount Candidates based on Keyword_Proximity to ["total", "grand total", "amount", "net", "الإجمالي", "المجموع", "الصافي"]
4. THE Invoice_Extractor SHALL reduce scores for amounts near ["subtotal", "tax", "vat", "discount", "ضريبة", "خصم"]
5. THE Invoice_Extractor SHALL score amount Candidates based on Document_Position (prefer bottom of document)
6. THE Invoice_Extractor SHALL prefer larger amounts when other factors are equal
7. THE Invoice_Extractor SHALL select the amount Candidate with the highest score
8. WHEN no valid amount is found, THE Invoice_Extractor SHALL return None with Confidence_Score 0.0
9. FOR ALL extracted amounts, the value SHALL be a valid positive number

### Requirement 5: Items and Quantities Extraction

**User Story:** As a developer, I want to extract item names, quantities, and prices from invoice lines, so that I can provide detailed invoice information.

#### Acceptance Criteria

1. WHEN a Line contains patterns like "2 x burger 50", THE Invoice_Extractor SHALL extract Item {name: "burger", quantity: 2, price: 50}
2. WHEN a Line contains patterns like "burger x2", THE Invoice_Extractor SHALL extract Item {name: "burger", quantity: 2, price: None}
3. WHEN a Line contains patterns like "milk 3 90", THE Invoice_Extractor SHALL extract Item {name: "milk", quantity: 3, price: 90}
4. THE Invoice_Extractor SHALL handle multi-word item names by grouping related tokens
5. THE Invoice_Extractor SHALL extract quantity as an integer when present
6. THE Invoice_Extractor SHALL extract price as a float when present
7. THE Invoice_Extractor SHALL handle items without explicit quantities (default quantity: 1)
8. THE Invoice_Extractor SHALL handle items without prices (price: None)
9. THE Invoice_Extractor SHALL return a list of all extracted Items
10. FOR ALL extracted Items, the name SHALL be a non-empty string and quantity SHALL be a positive integer

### Requirement 6: Category Classification

**User Story:** As a developer, I want to classify invoices into categories based on item keywords, so that I can organize and analyze invoices by type.

#### Acceptance Criteria

1. WHEN extracted Items or text contain keywords ["burger", "pizza", "cafe", "coffee", "sandwich", "meal"], THE Invoice_Extractor SHALL classify as "restaurant"
2. WHEN extracted Items or text contain keywords ["milk", "rice", "bread", "eggs", "vegetables"], THE Invoice_Extractor SHALL classify as "supermarket"
3. WHEN extracted Items or text contain keywords ["tablet", "medicine", "prescription", "drug"], THE Invoice_Extractor SHALL classify as "pharmacy"
4. WHEN extracted Items or text contain keywords ["fuel", "petrol", "diesel", "gas"], THE Invoice_Extractor SHALL classify as "gas_station"
5. WHEN extracted Items or text contain keywords ["shirt", "shoes", "clothing", "electronics"], THE Invoice_Extractor SHALL classify as "retail"
6. THE Invoice_Extractor SHALL support Arabic keywords for each category
7. THE Invoice_Extractor SHALL calculate a Confidence_Score for the category based on keyword match count
8. WHEN no clear category is identified, THE Invoice_Extractor SHALL return "general" with low Confidence_Score
9. THE Invoice_Extractor SHALL return the category with the highest keyword match count

### Requirement 7: Candidate Scoring System

**User Story:** As a developer, I want a unified scoring system for all field candidates, so that the best candidate for each field is selected consistently.

#### Acceptance Criteria

1. THE Scoring_Engine SHALL calculate scores for each Candidate based on multiple factors
2. THE Scoring_Engine SHALL score based on Keyword_Proximity (closer to relevant keywords = higher score)
3. THE Scoring_Engine SHALL score based on Document_Position (position preference varies by field type)
4. THE Scoring_Engine SHALL score based on format confidence (how well the value matches expected format)
5. THE Scoring_Engine SHALL score based on context words (presence of supporting context)
6. THE Scoring_Engine SHALL normalize all scores to range 0.0 to 1.0
7. THE Scoring_Engine SHALL combine multiple scoring factors using weighted average
8. THE Scoring_Engine SHALL select the Candidate with the highest combined score for each field
9. FOR ALL Candidates, the score SHALL be between 0.0 and 1.0 inclusive

### Requirement 8: Edge Case Handling

**User Story:** As a developer, I want the system to handle edge cases gracefully, so that extraction remains robust on diverse invoice formats.

#### Acceptance Criteria

1. WHEN multiple dates are present, THE Invoice_Extractor SHALL distinguish invoice dates from expiry dates and delivery dates
2. WHEN multiple amounts are present, THE Invoice_Extractor SHALL distinguish final totals from subtotals and taxes
3. WHEN OCR text is noisy or garbled, THE Invoice_Extractor SHALL process available information without crashing
4. WHEN a required field is missing, THE Invoice_Extractor SHALL return None with Confidence_Score 0.0 for that field
5. WHEN item patterns are ambiguous, THE Invoice_Extractor SHALL use context to disambiguate
6. THE Invoice_Extractor SHALL handle invoices with mixed Arabic and English content
7. THE Invoice_Extractor SHALL handle invoices with unusual formatting or layouts

### Requirement 9: Structured Output Format

**User Story:** As a developer, I want the extraction results in a structured JSON format with confidence scores, so that I can easily integrate the results into downstream systems.

#### Acceptance Criteria

1. THE Invoice_Extractor SHALL return results as a structured dictionary with keys: date, time, total, items, category
2. THE Invoice_Extractor SHALL include both value and Confidence_Score for each field
3. THE Invoice_Extractor SHALL format date values in ISO 8601 format (YYYY-MM-DD) when present
4. THE Invoice_Extractor SHALL format time values in HH:MM format when present
5. THE Invoice_Extractor SHALL format total as a float number when present
6. THE Invoice_Extractor SHALL format items as a list of dictionaries with keys: name, quantity, price
7. THE Invoice_Extractor SHALL format category as a string with its Confidence_Score
8. WHEN a field is not found, THE Invoice_Extractor SHALL include it with value None and Confidence_Score 0.0
9. THE Invoice_Extractor SHALL ensure the output is valid JSON-serializable

### Requirement 10: Modular Architecture

**User Story:** As a developer, I want a modular pipeline architecture with independent components, so that I can test, debug, and extend individual extraction modules.

#### Acceptance Criteria

1. THE Invoice_Extractor SHALL implement a Candidate class to represent candidates with value, score, and position
2. THE Invoice_Extractor SHALL provide separate extraction functions for each field type (date, time, total, items, category)
3. THE Invoice_Extractor SHALL provide a centralized Scoring_Engine for calculating candidate scores
4. THE Invoice_Extractor SHALL provide an orchestration pipeline that coordinates all extraction modules
5. THE Invoice_Extractor SHALL allow each module to be tested independently
6. THE Invoice_Extractor SHALL allow each module to be called independently for debugging
7. THE Invoice_Extractor SHALL use dependency injection for configuration and customization


### Requirement 11: Main Orchestrator Function

**User Story:** As a developer, I want a single function that orchestrates the complete extraction pipeline, so that I can extract all invoice fields with a simple API call.

#### Acceptance Criteria

1. THE Invoice_Extractor SHALL provide an extract_invoice function that accepts OCR_Text as input
2. THE extract_invoice function SHALL execute the pipeline in order: preprocess → extract candidates → score → select best
3. THE extract_invoice function SHALL extract all fields: date, time, total, items, category
4. THE extract_invoice function SHALL return a structured dictionary with all extracted fields and confidence scores
5. WHEN OCR_Text is empty or None, THE extract_invoice function SHALL return all fields as None with Confidence_Score 0.0
6. THE extract_invoice function SHALL complete processing within 3 seconds for typical invoice text (up to 10,000 characters)

### Requirement 12: Parser and Pretty Printer for Dates

**User Story:** As a developer, I want to parse extracted date strings into structured date objects and format them back to strings, so that I can verify correctness through round-trip testing.

#### Acceptance Criteria

1. WHEN a Valid_Date string is extracted, THE Date_Parser SHALL parse it into a datetime object
2. THE Date_Parser SHALL support all Date_Formats used in extraction (DD/MM/YYYY, YYYY-MM-DD, etc.)
3. THE Pretty_Printer SHALL format datetime objects back into standardized date strings (ISO 8601 format: YYYY-MM-DD)
4. FOR ALL Valid_Date strings, parsing then printing then parsing SHALL produce an equivalent datetime object (round-trip property)
5. THE Date_Parser SHALL handle month names in both English and Arabic

### Requirement 13: Error Handling and Validation

**User Story:** As a developer, I want the system to handle invalid inputs and processing errors gracefully, so that the application does not crash on malformed data.

#### Acceptance Criteria

1. WHEN OCR_Text is None, THE Invoice_Extractor SHALL return all fields as None with Confidence_Score 0.0 without raising an exception
2. WHEN OCR_Text is not a string type, THE Invoice_Extractor SHALL raise a TypeError with a descriptive message
3. IF an error occurs during field extraction, THEN THE Invoice_Extractor SHALL log the error and continue processing other fields
4. THE Invoice_Extractor SHALL handle Unicode characters and special symbols without raising encoding errors
5. WHEN OCR_Text exceeds 100,000 characters, THE Invoice_Extractor SHALL raise a ValueError indicating text is too long
6. THE Invoice_Extractor SHALL validate all extracted values before returning (dates are valid, amounts are positive, etc.)

### Requirement 14: Accuracy and Performance Targets

**User Story:** As a developer, I want the system to achieve high accuracy and performance on real invoice data, so that it can be reliably used in production.

#### Acceptance Criteria

1. THE Invoice_Extractor SHALL achieve at least 90% accuracy on date extraction from real invoices
2. THE Invoice_Extractor SHALL achieve at least 85% accuracy on total amount extraction from real invoices
3. THE Invoice_Extractor SHALL achieve at least 80% accuracy on items extraction from real invoices
4. THE Invoice_Extractor SHALL achieve at least 75% accuracy on category classification from real invoices
5. THE Invoice_Extractor SHALL process typical invoices (10,000 characters) in less than 3 seconds
6. WHEN the correct value is present in the text, THE Invoice_Extractor SHALL extract it with Confidence_Score >= 0.7 in at least 85% of cases
7. WHEN a field is not present, THE Invoice_Extractor SHALL return None with Confidence_Score < 0.3 in at least 80% of cases
