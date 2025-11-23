# Burp Suite Curl to HTTP Converter

A powerful and accurate Burp Suite extension that converts bash curl commands into properly formatted HTTP requests with real-time parsing and Repeater integration.

## Overview

**Curl to HTTP Converter** is a Burp Suite extension designed to streamline penetration testing and API security testing workflows. Instead of manually converting curl commands to HTTP requests, simply paste your curl command and instantly get a properly formatted HTTP request that you can edit, inspect, and send directly to Burp Repeater for further testing.

This extension is essential for security researchers, penetration testers, and developers who frequently work with curl commands and need to quickly convert them for testing in Burp Suite.

## Features

✅ **Real-time Curl Parsing** - Automatically converts curl commands as you type  
✅ **High Accuracy** - Comprehensive curl syntax support with robust error handling  
✅ **Full Curl Support** - Handles HTTP methods, headers, request bodies, cookies, user-agents, and more  
✅ **Editable Output** - Modify the converted HTTP request before sending  
✅ **Repeater Integration** - Send converted requests directly to Burp Repeater with one click  
✅ **Error Validation** - Validates curl syntax and displays meaningful error messages  
✅ **Clean UI** - Simple, intuitive interface with two panels (input and output)  

## Supported Curl Features

The extension accurately parses and converts the following curl options:

- **HTTP Methods**: `-X`, `--request` (GET, POST, PUT, DELETE, PATCH, etc.)
- **Headers**: `-H`, `--header` (custom headers, Content-Type, Authorization, etc.)
- **Request Body**: `-d`, `--data`, `--data-raw` (JSON, form data, etc.)
- **Cookies**: `-b`, `--cookie`
- **User-Agent**: `-A`, `--user-agent`
- **Compression**: `--compressed`
- **URLs**: Full URL parsing with path, query strings, ports, and protocols (HTTP/HTTPS)
- **Common Flags**: `-i`, `--include`, `-L`, `--location`, `-v`, `--verbose`

## Installation

### Prerequisites

- **Burp Suite** (Community Edition or Professional Edition)
- **Python 2.7** (Jython) or **Python 3.x** configured in Burp Suite

### Step-by-Step Installation

1. **Download the Extension**
   ```bash
   git clone https://github.com/Gauravjha68535/Curl-To-Repeater.git
   cd Curl-To-Repeater
   ```

2. **Open Burp Suite** and navigate to the **Extensions** tab (usually in the bottom panel)

3. **Click the "Add" Button** to load a new extension

4. **Configure the Extension**
   - **Extension type**: Select `Python`
   - **Extension file**: Click "Select file" and browse to `burp_curl_converter.py`
   - Click "Next"

5. **Click "Close"** once the extension loads successfully

6. **Verify Installation** - Look for a new tab labeled **"Curl Converter"** in your Burp Suite workspace (next to Repeater, Intruder, etc.)

## Usage

### Basic Workflow

1. **Open the "Curl Converter" Tab** in Burp Suite

2. **Paste a Curl Command** in the top-left section (input panel):
   ```bash
   curl -X POST https://api.example.com/users \
     -H "Content-Type: application/json" \
     -H "Authorization: Bearer token123" \
     -d '{"name":"John","email":"john@example.com"}'
   ```

3. **View the Converted HTTP Request** in the bottom section (output panel) - it will automatically appear as you type

4. **Edit if Needed** - Modify the HTTP request directly in the output panel

5. **Send to Repeater** - Click the **"Send to Repeater"** button to send the request directly to Burp's Repeater tool for testing

6. **Clear** - Click the **"Clear"** button to reset both panels

### Example Conversions

**Example 1: Simple GET Request**
```
Input:  curl https://example.com
Output: GET / HTTP/1.1
        Host: example.com
```

**Example 2: POST Request with JSON**
```
Input:  curl -X POST https://api.example.com/api -H "Content-Type: application/json" -d '{"key":"value"}'
Output: POST /api HTTP/1.1
        Host: api.example.com
        Content-Type: application/json
        Content-Length: 16

        {"key":"value"}
```

**Example 3: Request with Custom Headers**
```
Input:  curl -X GET https://example.com -H "Authorization: Bearer token" -H "User-Agent: MyApp/1.0"
Output: GET / HTTP/1.1
        Host: example.com
        Authorization: Bearer token
        User-Agent: MyApp/1.0
```

## Error Handling

The extension validates curl syntax and provides clear error messages:

- **"Invalid curl command"** - The command doesn't start with `curl`
- **"Parsing error: ..."** - Syntax error in the curl command
- **"No URL found in curl command"** - Missing URL in the curl request
- **"Invalid URL"** - The URL is malformed or incomplete
- **"Unsupported protocol: ..."** - Uses a protocol other than HTTP or HTTPS

## Technical Details

- **Language**: Python (Jython-compatible)
- **Burp API**: Uses Burp Suite's standard extension API
- **URL Parsing**: Java's `URL` class for accurate URL parsing
- **Curl Parsing**: Python's `shlex` module for proper handling of quoted strings and complex syntax
- **Request Conversion**: Follows HTTP/1.1 RFC standards

## How It Works

1. **Curl Parsing** - The extension uses Python's `shlex` module to properly tokenize curl commands while handling quoted strings and escape sequences
2. **URL Processing** - Java's URL class parses the URL to extract scheme, host, port, path, and query parameters
3. **HTTP Construction** - Builds a proper HTTP/1.1 request with correct formatting, headers, and body
4. **Repeater Integration** - Sends the binary request directly to Burp Repeater for further manipulation and testing

## Advantages Over Manual Conversion

- **Speed** - Convert complex curl commands in seconds
- **Accuracy** - No manual errors in header formatting or URL encoding
- **Consistency** - Always produces RFC-compliant HTTP requests
- **Integration** - Seamlessly integrates with Burp's existing tools
- **Security** - Keep your workflow within Burp Suite without external tools

## Troubleshooting

**Extension doesn't load:**
- Ensure Python is properly configured in Burp Suite (Extensions → Options → Python Environment)
- Check that the file path contains no special characters
- Verify you're using the correct Python version (Python 2.7 for older Burp versions)

**"Send to Repeater" button doesn't work:**
- Ensure the curl command is valid and converted without errors
- Check that the HTTP request output doesn't show an error message
- Verify Burp Suite has network connectivity

**Curl command not converting correctly:**
- Ensure quotes are properly escaped in your curl command
- Check that all required parameters are included
- Verify the URL is complete (includes protocol and host)

## Security Considerations

- The extension processes curl commands locally within Burp Suite
- No data is sent to external servers
- All sensitive information (tokens, passwords, API keys) in your requests stays within Burp Suite
- Use this tool only on systems and targets you have permission to test

## Contributing

Contributions are welcome! Please feel free to:
- Report bugs and issues
- Suggest new features
- Submit pull requests with improvements

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Disclaimer

This tool is designed for authorized security testing and penetration testing purposes only. Unauthorized access to computer systems is illegal. Always obtain proper authorization before testing any systems or APIs. The author is not responsible for any misuse or damage caused by this tool.

## Support

For issues, feature requests, or questions:
- Open an issue on GitHub
- Check existing issues for solutions
- Provide detailed information about the curl command causing issues

---

**Happy Testing! 🔒**
