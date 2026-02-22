from burp import IBurpExtender, ITab
from javax.swing import (JPanel, JTextArea, JButton, JSplitPane, JScrollPane, 
                        JLabel, SwingUtilities, BorderFactory, JOptionPane, Timer)
from javax.swing.event import DocumentListener
from java.awt import BorderLayout, Color, Toolkit
from java.awt.event import ActionListener as SwingActionListener
from java.awt.datatransfer import StringSelection
from java.net import URL
from java.io import File
import shlex
import re
import base64
import traceback
import os

# Python 2/3 compatible urllib import for Jython
try:
    from urllib import quote, unquote  # Jython/Python 2
except ImportError:
    from urllib.parse import quote, unquote  # Python 3 fallback


class BurpExtender(IBurpExtender, ITab, SwingActionListener, DocumentListener):
    
    def registerExtenderCallbacks(self, callbacks):
        self._callbacks = callbacks
        self._helpers = callbacks.getHelpers()
        self.panel = None
        self._lastParsed = None  # Cache last successful parse
        self._history = []  # Command history
        self._history_index = -1
        self._initUI()
        callbacks.addSuiteTab(self)
        callbacks.printOutput("✓ Curl Converter extension loaded successfully")
    
    def _initUI(self):
        self.panel = JPanel(BorderLayout())
        self.panel.setBorder(BorderFactory.createEmptyBorder(5, 5, 5, 5))
        
        # Top panel - Input
        top_panel = JPanel(BorderLayout())
        top_label = JLabel("Paste Curl Command:")
        self.curl_input = JTextArea(10, 60)
        self.curl_input.setLineWrap(True)
        self.curl_input.setWrapStyleWord(True)
        self.curl_input.setFont(self.curl_input.getFont().deriveFont(12.0))
        self.curl_input.getDocument().addDocumentListener(self)
        
        # Add key listener for history navigation
        from java.awt.event import KeyAdapter, KeyEvent
        def on_key_pressed(e):
            if e.getKeyCode() == KeyEvent.VK_UP:
                self._navigateHistory(-1)
            elif e.getKeyCode() == KeyEvent.VK_DOWN:
                self._navigateHistory(1)
        self.curl_input.addKeyListener(KeyAdapter(keyPressed=on_key_pressed))
        
        curl_scroll = JScrollPane(self.curl_input)
        curl_scroll.setBorder(BorderFactory.createTitledBorder("Input"))
        
        top_panel.add(top_label, BorderLayout.NORTH)
        top_panel.add(curl_scroll, BorderLayout.CENTER)
        
        # Bottom panel - Output
        bottom_panel = JPanel(BorderLayout())
        bottom_label = JLabel("Converted HTTP Request:")
        self.http_output = JTextArea(10, 60)
        self.http_output.setLineWrap(False)
        self.http_output.setFont(self.http_output.getFont().deriveFont(12.0))
        self.http_output.setEditable(True)
        http_scroll = JScrollPane(self.http_output)
        http_scroll.setBorder(BorderFactory.createTitledBorder("Output"))
        
        # Buttons panel
        buttons_panel = JPanel()
        self.send_to_repeater_btn = JButton("Send to Repeater", actionPerformed=self._sendToRepeater)
        self.send_to_intruder_btn = JButton("Send to Intruder", actionPerformed=self._sendToIntruder)
        self.copy_btn = JButton("Copy to Clipboard", actionPerformed=self._copyToClipboard)
        self.clear_btn = JButton("Clear", actionPerformed=self._clear)
        
        buttons_panel.add(self.send_to_repeater_btn)
        buttons_panel.add(self.send_to_intruder_btn)
        buttons_panel.add(self.copy_btn)
        buttons_panel.add(self.clear_btn)
        
        bottom_panel.add(bottom_label, BorderLayout.NORTH)
        bottom_panel.add(http_scroll, BorderLayout.CENTER)
        bottom_panel.add(buttons_panel, BorderLayout.SOUTH)
        
        # Split pane
        split_pane = JSplitPane(JSplitPane.VERTICAL_SPLIT, top_panel, bottom_panel)
        split_pane.setDividerLocation(200)
        split_pane.setResizeWeight(0.5)
        
        self.panel.add(split_pane, BorderLayout.CENTER)
        
        # Status label
        self.status_label = JLabel("Ready")
        self.status_label.setForeground(Color.GRAY)
        self.panel.add(self.status_label, BorderLayout.SOUTH)
        
        # Debounce timer for parsing (300ms delay)
        self._parse_timer = Timer(300, self)
        self._parse_timer.setRepeats(False)
    
    def _navigateHistory(self, direction):
        """Navigate command history with arrow keys"""
        if not self._history:
            return
        self._history_index += direction
        self._history_index = max(0, min(self._history_index, len(self._history) - 1))
        self.curl_input.setText(self._history[self._history_index])
        self.curl_input.setCaretPosition(self.curl_input.getDocument().getLength())
    
    def _parseURL(self, url_str):
        """Parse URL and return components with proper default port handling"""
        try:
            # Handle protocol-relative URLs
            if url_str.startswith('//'):
                url_str = 'http:' + url_str
            
            # Handle missing protocol
            if '://' not in url_str:
                url_str = 'http://' + url_str
            
            java_url = URL(url_str)
            protocol = str(java_url.getProtocol()).lower()
            port = java_url.getPort()
            
            # Set default ports
            if port == -1:
                port = 443 if protocol == 'https' else 80
            
            return {
                'scheme': protocol,
                'host': str(java_url.getHost()),
                'port': port,
                'path': str(java_url.getPath()) if java_url.getPath() else '/',
                'query': str(java_url.getQuery()) if java_url.getQuery() else None,
                'file': str(java_url.getFile())
            }
        except Exception as e:
            self._callbacks.printError("URL parsing error: " + str(e))
            return None
    
    def _readFileData(self, filepath):
        """Safely read file contents for @filename syntax"""
        try:
            # Remove surrounding quotes if present
            filepath = filepath.strip('"\'')
            
            # Security: warn about absolute paths or path traversal
            if os.path.isabs(filepath) or '..' in filepath:
                self._callbacks.printOutput(
                    f"⚠ Warning: File path '{filepath}' - ensure this is intended and safe"
                )
            
            file_obj = File(filepath)
            if not file_obj.exists() or not file_obj.canRead():
                return None, f"Cannot read file: {filepath}"
            
            # Read file as bytes then decode
            with open(filepath, 'rb') as f:
                content = f.read()
            return content.decode('utf-8', errors='replace'), None
            
        except Exception as e:
            return None, f"Error reading file: {str(e)}"
    
    def _parseCurl(self, curl_cmd):
        """Enhanced curl parser with support for more options"""
        try:
            curl_cmd = curl_cmd.strip()
            if not curl_cmd:
                return None, "Empty command"
            
            # Remove 'curl' prefix case-insensitively
            if not curl_cmd.lower().startswith('curl'):
                return None, "Command must start with 'curl'"
            
            curl_cmd = curl_cmd[4:].strip()
            
            # Handle common copy-paste issues
            curl_cmd = curl_cmd.replace('\\\n', ' ').replace('\\\r\n', ' ')
            curl_cmd = re.sub(r'\s+', ' ', curl_cmd)  # Normalize whitespace
            
            url = None
            method = "GET"
            headers = {}
            data_parts = []  # Support multiple -d flags
            data_binary = None
            auth = None
            insecure = False
            follow_redirects = False
            form_data = []  # For -F/--form
            
            # Custom shlex-like parsing to handle @filename syntax better
            try:
                tokens = shlex.split(curl_cmd)
            except ValueError as e:
                # Fallback: simple split if shlex fails
                self._callbacks.printOutput(f"Warning: shlex failed, using fallback: {e}")
                tokens = curl_cmd.split()
            
            i = 0
            while i < len(tokens):
                token = tokens[i]
                
                if token in ('-X', '--request'):
                    i += 1
                    if i < len(tokens):
                        method = tokens[i].upper()
                
                elif token in ('-H', '--header'):
                    i += 1
                    if i < len(tokens):
                        header = tokens[i]
                        if ':' in header:
                            key, value = header.split(':', 1)
                            key, value = key.strip(), value.strip()
                            # Handle duplicate headers (e.g., multiple Cookie values)
                            if key.lower() == 'cookie' and key in headers:
                                headers[key] += '; ' + value
                            else:
                                headers[key] = value
                
                elif token in ('-d', '--data', '--data-raw', '--data-ascii'):
                    i += 1
                    if i < len(tokens):
                        data_val = tokens[i]
                        # Handle @filename syntax
                        if data_val.startswith('@'):
                            content, error = self._readFileData(data_val[1:])
                            if error:
                                return None, error
                            data_parts.append(content)
                        else:
                            data_parts.append(data_val)
                        if method == "GET":
                            method = "POST"
                
                elif token == '--data-binary':
                    i += 1
                    if i < len(tokens):
                        data_val = tokens[i]
                        if data_val.startswith('@'):
                            content, error = self._readFileData(data_val[1:])
                            if error:
                                return None, error
                            data_parts.append(content)
                        else:
                            data_parts.append(data_val)
                        data_binary = True
                        if method == "GET":
                            method = "POST"
                
                elif token == '--data-urlencode':
                    i += 1
                    if i < len(tokens):
                        # Handle key=value@file or just value
                        val = tokens[i]
                        if '@' in val and not val.startswith('@'):
                            # key=value@file format
                            key, rest = val.split('=', 1)
                            if rest.startswith('@'):
                                content, error = self._readFileData(rest[1:])
                                if error:
                                    return None, error
                                encoded = quote(content, safe='')
                                data_parts.append(f"{key}={encoded}")
                            else:
                                data_parts.append(f"{key}={quote(rest, safe='')}")
                        else:
                            data_parts.append(quote(val, safe=''))
                        if method == "GET":
                            method = "POST"
                
                elif token in ('-F', '--form'):
                    i += 1
                    if i < len(tokens):
                        form_data.append(tokens[i])
                        if method == "GET":
                            method = "POST"
                        # Note: Full multipart support is complex; warn user
                        self._callbacks.printOutput(
                            "⚠ Warning: --form/-F creates multipart/form-data - "
                            "Burp may need manual Content-Type adjustment"
                        )
                
                elif token in ('-b', '--cookie'):
                    i += 1
                    if i < len(tokens):
                        cookie_val = tokens[i]
                        # Handle @filename for cookies too
                        if cookie_val.startswith('@'):
                            content, error = self._readFileData(cookie_val[1:])
                            if error:
                                return None, error
                            headers['Cookie'] = content.strip()
                        else:
                            headers['Cookie'] = cookie_val
                
                elif token in ('-A', '--user-agent'):
                    i += 1
                    if i < len(tokens):
                        headers['User-Agent'] = tokens[i]
                
                elif token in ('-u', '--user'):
                    i += 1
                    if i < len(tokens):
                        auth = tokens[i]
                        # Add Basic Auth header
                        encoded = base64.b64encode(auth.encode('utf-8')).decode('utf-8')
                        headers['Authorization'] = 'Basic ' + encoded
                
                elif token in ('-e', '--referer'):
                    i += 1
                    if i < len(tokens):
                        headers['Referer'] = tokens[i]
                
                elif token == '--compressed':
                    headers['Accept-Encoding'] = 'gzip, deflate'
                
                elif token in ('-L', '--location'):
                    follow_redirects = True
                
                elif token in ('-k', '--insecure'):
                    insecure = True
                
                elif token in ('-I', '--head'):
                    method = "HEAD"
                
                elif token in ('-G', '--get'):
                    method = "GET"
                    # Move data to query string if present
                    if data_parts:
                        query_part = '&'.join(data_parts)
                        # This would need URL reconstruction - simplified warning
                        self._callbacks.printOutput(
                            "⚠ Warning: -G with -d moves data to query string - "
                            "manual adjustment may be needed"
                        )
                
                elif token.startswith('-') and len(token) > 1:
                    # Unknown flag - skip it and its value if next token isn't a flag
                    if i + 1 < len(tokens) and not tokens[i + 1].startswith('-'):
                        i += 1  # Skip the value
                
                else:
                    # Positional argument - should be URL
                    if url is None and not token.startswith('-'):
                        url = token.strip('"\'')
                
                i += 1
            
            if not url:
                return None, "No URL found in curl command"
            
            # Combine multiple data parts
            data = None
            if data_parts:
                data = '&'.join(data_parts)
                if 'Content-Type' not in headers and not data_binary:
                    headers['Content-Type'] = 'application/x-www-form-urlencoded'
            
            # Warn about unsupported/partially supported features
            warnings = []
            if follow_redirects:
                warnings.append("Follow redirects (-L) not supported - request shows initial URL only")
            if insecure:
                warnings.append("SSL verification disabled (-k) - ensure Burp CA is installed")
            if form_data:
                warnings.append(f"--form/-F detected ({len(form_data)} fields) - multipart boundaries may need adjustment in Burp")
            
            result = {
                'url': url,
                'method': method,
                'headers': headers,
                'data': data,
                'data_binary': data_binary,
                'warnings': warnings,
                'auth': auth,
                'insecure': insecure,
                'form_data': form_data if form_data else None
            }
            
            return result, None
        
        except Exception as e:
            self._callbacks.printError("Parse exception: " + traceback.format_exc())
            return None, "Parsing error: " + str(e)
    
    def _buildHttpRequest(self, parsed):
        """Build raw HTTP request from parsed curl command"""
        try:
            url = parsed['url']
            method = parsed['method']
            headers = parsed['headers'].copy()
            data = parsed['data']
            data_binary = parsed.get('data_binary', False)
            
            parsed_url = self._parseURL(url)
            if not parsed_url:
                return None, "Invalid URL format"
            
            host = parsed_url['host']
            port = parsed_url['port']
            protocol = parsed_url['scheme']
            path = parsed_url['path']
            
            if parsed_url['query']:
                path += '?' + parsed_url['query']
            
            # Build request line
            request_lines = [f"{method} {path} HTTP/1.1"]
            
            # Ensure Host header (with IPv6 bracketing)
            if 'Host' not in headers:
                host_header = host
                # Bracket IPv6 addresses
                if ':' in host and not host.startswith('['):
                    host_header = f"[{host}]"
                if (protocol == 'https' and port != 443) or (protocol == 'http' and port != 80):
                    host_header += f":{port}"
                headers['Host'] = host_header
            
            # Handle body data
            if data and method in ('POST', 'PUT', 'PATCH', 'DELETE'):
                # Calculate Content-Length using BYTE length, not string length
                if isinstance(data, str):
                    data_bytes = data.encode('utf-8')
                else:
                    data_bytes = data  # Already bytes
                
                if 'Content-Length' not in headers:
                    headers['Content-Length'] = str(len(data_bytes))
                
                # Set Content-Type if not present and not binary
                if 'Content-Type' not in headers and not data_binary:
                    headers['Content-Type'] = 'application/x-www-form-urlencoded'
            
            # Add headers in order (Host first, then others)
            if 'Host' in headers:
                request_lines.append(f"Host: {headers.pop('Host')}")
            for key, value in headers.items():
                request_lines.append(f"{key}: {value}")
            
            # Empty line before body
            request_lines.append("")
            
            # Add body if present
            if data:
                request_lines.append(data)
            
            http_request = "\r\n".join(request_lines)
            return http_request, None
        
        except Exception as e:
            self._callbacks.printError("Build exception: " + traceback.format_exc())
            return None, "Error building request: " + str(e)
    
    def _updateStatus(self, message, is_error=False):
        """Update status label safely on EDT"""
        def update():
            self.status_label.setText(message)
            self.status_label.setForeground(Color.RED if is_error else Color.GRAY)
        SwingUtilities.invokeLater(update)
    
    # DocumentListener methods
    def changedUpdate(self, e):
        pass  # Not used for plain text
    
    def insertUpdate(self, e):
        self._parse_timer.restart()  # Debounce parsing
    
    def removeUpdate(self, e):
        self._parse_timer.restart()  # Debounce parsing
    
    # Timer ActionListener for debounced parsing
    def actionPerformed(self, e=None):
        """Called by Timer - runs parsing off EDT"""
        SwingUtilities.invokeLater(self._convertCurl)
    
    def _convertCurl(self):
        """Convert curl to HTTP with error handling"""
        try:
            curl_text = self.curl_input.getText().strip()
            
            if not curl_text:
                self.http_output.setText("")
                self._lastParsed = None
                self._updateStatus("Ready")
                return
            
            # Input size validation
            if len(curl_text) > 100000:  # 100KB limit
                self.http_output.setText("# Error: Input too large (max 100KB)")
                self._updateStatus("Input too large", True)
                return
            
            parsed, error = self._parseCurl(curl_text)
            
            if error:
                self.http_output.setText(f"# Error: {error}")
                self._lastParsed = None
                self._updateStatus("Parse error", True)
                return
            
            http_request, error = self._buildHttpRequest(parsed)
            
            if error:
                self.http_output.setText(f"# Error: {error}")
                self._lastParsed = None
                self._updateStatus("Build error", True)
                return
            
            # Build output with warnings as comments
            output_lines = []
            if parsed.get('warnings'):
                output_lines.append("# ⚠ Warnings:")
                for warning in parsed['warnings']:
                    output_lines.append(f"#   • {warning}")
                output_lines.append("")
            
            output_lines.append(http_request)
            self.http_output.setText("\n".join(output_lines))
            
            # Update history (avoid duplicates at end)
            if curl_text and (not self._history or self._history[-1] != curl_text):
                self._history.append(curl_text)
                if len(self._history) > 50:  # Limit history size
                    self._history.pop(0)
                self._history_index = len(self._history)  # Reset to end
            
            self._lastParsed = parsed
            self._updateStatus("✓ Converted successfully")
            
        except Exception as e:
            error_msg = f"# Unexpected error: {str(e)}"
            self.http_output.setText(error_msg)
            self._callbacks.printError("Conversion error: " + traceback.format_exc())
            self._updateStatus("Unexpected error", True)
    
    def _getCleanRequestBytes(self):
        """Extract clean HTTP request bytes from output, rebuilding if possible"""
        output_text = self.http_output.getText()
        
        if not output_text or output_text.strip().startswith("# Error"):
            return None
        
        # Prefer rebuilding from parsed data for accuracy
        if self._lastParsed:
            http_request, error = self._buildHttpRequest(self._lastParsed)
            if not error and http_request:
                return http_request.encode('utf-8')
        
        # Fallback: parse the displayed output
        # Skip comment lines at the top
        lines = output_text.split('\n')
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip() and not line.startswith('#'):
                start_idx = i
                break
        
        request_text = '\n'.join(lines[start_idx:]).strip()
        if not request_text:
            return None
        
        # Ensure proper CRLF line endings for HTTP
        request_text = request_text.replace('\r\n', '\n').replace('\n', '\r\n')
        return request_text.encode('utf-8')
    
    def _sendToRepeater(self, e):
        """Send current request to Repeater"""
        self._sendToTool("Repeater", 
                        lambda host, port, https, req: 
                            self._callbacks.sendToRepeater(host, port, https, req, "Curl Request"))
    
    def _sendToIntruder(self, e):
        """Send current request to Intruder"""
        self._sendToTool("Intruder",
                        lambda host, port, https, req:
                            self._callbacks.sendToIntruder(host, port, https, req, None))
    
    def _sendToTool(self, tool_name, send_func):
        """Generic sender with validation and proper request extraction"""
        try:
            request_bytes = self._getCleanRequestBytes()
            
            if not request_bytes:
                JOptionPane.showMessageDialog(
                    self.panel, 
                    "No valid request to send. Check for errors in the output.", 
                    "Error", JOptionPane.ERROR_MESSAGE
                )
                self._updateStatus("Cannot send: invalid request", True)
                return
            
            if not self._lastParsed:
                # Try to re-parse current input as fallback
                curl_text = self.curl_input.getText().strip()
                if curl_text:
                    parsed, error = self._parseCurl(curl_text)
                    if not error:
                        self._lastParsed = parsed
            
            # Extract target info
            if self._lastParsed:
                parsed_url = self._parseURL(self._lastParsed['url'])
                if not parsed_url:
                    raise Exception("Invalid URL in parsed data")
                host = parsed_url['host']
                port = parsed_url['port']
                use_https = parsed_url['scheme'] == 'https'
            else:
                # Last resort: try to extract from request bytes
                request_str = request_bytes.decode('utf-8', errors='ignore')
                host_match = re.search(r'Host:\s*([^\r\n]+)', request_str, re.I)
                if not host_match:
                    raise Exception("Cannot determine target host")
                
                host_header = host_match.group(1).strip()
                if ':' in host_header and not host_header.startswith('['):
                    # Could be IPv6 or host:port
                    if host_header.count(':') == 1:
                        host, port_str = host_header.rsplit(':', 1)
                        port = int(port_str)
                    else:
                        host = host_header
                        port = 443  # Default guess
                else:
                    host = host_header
                    port = 443  # Default guess
                use_https = port == 443  # Simplified assumption
            
            # Send to tool
            send_func(host, port, use_https, request_bytes)
            self._updateStatus(f"✓ Sent to {tool_name}")
            
        except Exception as e:
            error_msg = f"Error sending to {tool_name}: {str(e)}"
            JOptionPane.showMessageDialog(
                self.panel, 
                error_msg, 
                "Error", JOptionPane.ERROR_MESSAGE
            )
            self._callbacks.printError("Send error: " + traceback.format_exc())
            self._updateStatus("Send failed", True)
    
    def _copyToClipboard(self, e):
        """Copy output to clipboard (clean version without comments)"""
        try:
            request_bytes = self._getCleanRequestBytes()
            if not request_bytes:
                self._updateStatus("Nothing to copy", True)
                return
            
            clean_text = request_bytes.decode('utf-8')
            selection = StringSelection(clean_text)
            clipboard = Toolkit.getDefaultToolkit().getSystemClipboard()
            clipboard.setContents(selection, None)
            self._updateStatus("✓ Copied to clipboard")
            
        except Exception as e:
            self._callbacks.printError("Copy error: " + str(e))
            self._updateStatus("Copy failed", True)
    
    def _clear(self, e):
        """Clear all fields and reset state"""
        self.curl_input.setText("")
        self.http_output.setText("")
        self._lastParsed = None
        self._history_index = -1
        self._updateStatus("Cleared")
        self.curl_input.requestFocus()
    
    # ITab interface
    def getUiComponent(self):
        return self.panel
    
    def getTabCaption(self):
        return "cURL Converter"
