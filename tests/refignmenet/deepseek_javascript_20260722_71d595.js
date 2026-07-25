// Field definition with validation
{
  id: 'address',
  label: 'IP Address / Hostname',
  type: 'ip-address',  // ← Special type
  required: true,
  validation: {
    pattern: '^(\\d{1,3}\\.){3}\\d{1,3}$|^[a-zA-Z0-9.-]+$',
    message: 'Enter a valid IP address or hostname',
  }
}