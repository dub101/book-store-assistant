# Book Store Assistant

Python tool to transform a CSV of ISBNs into a Geslib-ready Excel file with completed book metadata.

## Version 1 Scope

Input:
- CSV file with one ISBN per row

Output:
- Excel file ready for Geslib import

Target columns:
- ISBN
- Title
- Subtitle
- Author
- Editorial
- Synopsis
- Subject
- CoverURL

## Rules

- ISBN, Title, Author, Editorial, Synopsis, and Subject are mandatory
- Subtitle is included only when relevant
- Synopsis must be in Spanish
- If the book is in another language, synopsis must include Spanish first and then the original language
- Subject must be selected from the bookstore's internal list
- Cover image is provided as a URL

## Approach

The system will:
1. Read ISBNs from CSV
2. Retrieve metadata from trusted web sources
3. Resolve deterministic fields with rules
4. Use AI only for controlled enrichment tasks such as synopsis formatting and subject suggestion
5. Export the final dataset to Excel for Geslib import
