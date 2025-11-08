# Test MCP Server with curl

## Health Check
```bash
curl http://localhost:8000/health
```

Expected response:
```json
{"status":"healthy","service":"agent-extractor"}
```

## Extract Document Data

### Example 1: Simple Invoice Extraction
```bash
curl -X POST http://localhost:8000/extract_document_data \
  -H "Content-Type: application/json" \
  -d '{
    "documentBase64": "JVBERi0xLjQKJeLjz9MKMyAwIG9iago8PC9UeXBlIC9QYWdlCi9QYXJlbnQgMSAwIFIKL01lZGlhQm94IFswIDAgNjEyIDc5Ml0KL0NvbnRlbnRzIDQgMCBSCi9SZXNvdXJjZXMgPDwKL0ZvbnQgPDwKL0YxIDUgMCBSCj4+Cj4+Cj4+CmVuZG9iago0IDAgb2JqCjw8L0xlbmd0aCA0Nj4+CnN0cmVhbQpCVAovRjEgMjQgVGYKMTAwIDcwMCBUZAooSW52b2ljZSAjMTIzNDUpIFRqCkVUCmVuZHN0cmVhbQplbmRvYmoKNSAwIG9iago8PC9UeXBlIC9Gb250Ci9TdWJ0eXBlIC9UeXBlMQovQmFzZUZvbnQgL0hlbHZldGljYQo+PgplbmRvYmoKMSAwIG9iago8PC9UeXBlIC9QYWdlcwovS2lkcyBbMyAwIFJdCi9Db3VudCAxCj4+CmVuZG9iagoyIDAgb2JqCjw8L1R5cGUgL0NhdGFsb2cKL1BhZ2VzIDEgMCBSCj4+CmVuZG9iagp4cmVmCjAgNgowMDAwMDAwMDAwIDY1NTM1IGYgCjAwMDAwMDAyOTQgMDAwMDAgbiAKMDAwMDAwMDM1MSAwMDAwMCBuIAowMDAwMDAwMDA5IDAwMDAwIG4gCjAwMDAwMDAxMzIgMDAwMDAgbiAKMDAwMDAwMDIyOCAwMDAwMCBuIAp0cmFpbGVyCjw8L1NpemUgNgovUm9vdCAyIDAgUgo+PgpzdGFydHhyZWYKNDAwCiUlRU9G",
    "fileType": "pdf",
    "dataElements": [
      {
        "name": "invoiceNumber",
        "description": "The invoice number from the document",
        "format": "string",
        "required": true
      }
    ]
  }'
```

### Example 2: Multiple Fields
```bash
curl -X POST http://localhost:8000/extract_document_data \
  -H "Content-Type: application/json" \
  -d '{
    "documentBase64": "<YOUR_BASE64_PDF>",
    "fileType": "pdf",
    "dataElements": [
      {
        "name": "invoiceNumber",
        "description": "Invoice number",
        "format": "string",
        "required": true
      },
      {
        "name": "totalAmount",
        "description": "Total amount due",
        "format": "number",
        "required": true
      },
      {
        "name": "dueDate",
        "description": "Payment due date",
        "format": "date",
        "required": false
      }
    ]
  }'
```

Expected success response:
```json
{
  "success": true,
  "extractedData": {
    "invoiceNumber": "12345",
    "totalAmount": 1500.00,
    "dueDate": "2025-12-31"
  },
  "errors": null
}
```

Expected failure response (missing required field):
```json
{
  "success": false,
  "extractedData": {},
  "errors": ["Required field 'invoiceNumber' not found in document"]
}
```

## PowerShell Examples

### Health Check
```powershell
Invoke-RestMethod -Uri http://localhost:8000/health -Method Get
```

### Extract Data
```powershell
$body = @{
    documentBase64 = "JVBERi0xLjQK..."
    fileType = "pdf"
    dataElements = @(
        @{
            name = "invoiceNumber"
            description = "Invoice number"
            format = "string"
            required = $true
        }
    )
} | ConvertTo-Json -Depth 10

Invoke-RestMethod -Uri http://localhost:8000/extract_document_data -Method Post -Body $body -ContentType "application/json"
```
