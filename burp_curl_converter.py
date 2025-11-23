from burp import IBurpExtender, ITab
from javax.swing import JPanel, JTextArea, JButton, JSplitPane, JScrollPane, JLabel
from javax.swing.event import DocumentListener
from java.awt import BorderLayout
from java.awt.event import ActionListener
from java.net import URL
import shlex

class BurpExtender(IBurpExtender, ITab, ActionListener, DocumentListener):
    
    def registerExtenderCallbacks(self, callbacks):
        self._callbacks = callbacks
        self._helpers = callbacks.getHelpers()
        self.panel = None
        self._initUI()
        callbacks.addSuiteTab(self)
    
    def _initUI(self):
        self.panel = JPanel(BorderLayout())
        
        top_panel = JPanel(BorderLayout())
        top_label = JLabel("Paste Curl Request:")
        self.curl_input = JTextArea(10, 50)
        self.curl_input.setLineWrap(True)
        self.curl_input.setWrapStyleWord(True)
        self.curl_input.getDocument().addDocumentListener(self)
        curl_scroll = JScrollPane(self.curl_input)
        
        top_panel.add(top_label, BorderLayout.NORTH)
        top_panel.add(curl_scroll, BorderLayout.CENTER)
        
        bottom_panel = JPanel(BorderLayout())
        bottom_label = JLabel("Converted HTTP Request:")
        self.http_output = JTextArea(10, 50)
        self.http_output.setLineWrap(True)
        self.http_output.setWrapStyleWord(True)
        self.http_output.setEditable(True)
        http_scroll = JScrollPane(self.http_output)
        
        buttons_panel = JPanel()
        self.send_to_repeater_btn = JButton("Send to Repeater", actionPerformed=self._sendToRepeater)
        self.clear_btn = JButton("Clear", actionPerformed=self._clear)
        buttons_panel.add(self.send_to_repeater_btn)
        buttons_panel.add(self.clear_btn)
        
        bottom_panel.add(bottom_label, BorderLayout.NORTH)
        bottom_panel.add(http_scroll, BorderLayout.CENTER)
        bottom_panel.add(buttons_panel, BorderLayout.SOUTH)
        
        split_pane = JSplitPane(JSplitPane.VERTICAL_SPLIT, top_panel, bottom_panel)
        split_pane.setDividerLocation(0.5)
        
        self.panel.add(split_pane, BorderLayout.CENTER)
    
    def _parseURL(self, url_str):
        try:
            java_url = URL(url_str)
            return {
                'scheme': str(java_url.getProtocol()),
                'host': str(java_url.getHost()),
                'port': java_url.getPort(),
                'path': str(java_url.getPath()) if java_url.getPath() else '',
                'query': str(java_url.getQuery()) if java_url.getQuery() else None
            }
        except Exception as e:
            return None
    
    def _parseCurl(self, curl_cmd):
        try:
            curl_cmd = curl_cmd.strip()
            if not curl_cmd.lower().startswith('curl'):
                return None, "Invalid curl command"
            
            curl_cmd = curl_cmd[4:].strip()
            
            url = None
            method = "GET"
            headers = {}
            data = None
            
            try:
                tokens = shlex.split(curl_cmd)
            except ValueError as e:
                return None, "Parsing error: " + str(e)
            
            i = 0
            while i < len(tokens):
                token = tokens[i]
                
                if token == '-X' or token == '--request':
                    i += 1
                    if i < len(tokens):
                        method = tokens[i].upper()
                
                elif token == '-H' or token == '--header':
                    i += 1
                    if i < len(tokens):
                        header = tokens[i]
                        if ':' in header:
                            key, value = header.split(':', 1)
                            headers[key.strip()] = value.strip()
                
                elif token == '-d' or token == '--data' or token == '--data-raw':
                    i += 1
                    if i < len(tokens):
                        data = tokens[i]
                
                elif token == '-b' or token == '--cookie':
                    i += 1
                    if i < len(tokens):
                        headers['Cookie'] = tokens[i]
                
                elif token == '-A' or token == '--user-agent':
                    i += 1
                    if i < len(tokens):
                        headers['User-Agent'] = tokens[i]
                
                elif token == '--compressed':
                    headers['Accept-Encoding'] = 'gzip, deflate'
                
                elif not token.startswith('-'):
                    if url is None:
                        url = token
                
                i += 1
            
            if not url:
                return None, "No URL found in curl command"
            
            return {
                'url': url,
                'method': method,
                'headers': headers,
                'data': data
            }, None
        
        except Exception as e:
            return None, "Error: " + str(e)
    
    def _buildHttpRequest(self, parsed):
        try:
            url = parsed['url']
            method = parsed['method']
            headers = parsed['headers']
            data = parsed['data']
            
            parsed_url = self._parseURL(url)
            
            if not parsed_url:
                return None, "Invalid URL"
            
            host = parsed_url['host']
            port = parsed_url['port']
            protocol = parsed_url['scheme'].lower()
            
            if not host:
                return None, "Invalid URL"
            
            if protocol not in ['http', 'https']:
                return None, "Unsupported protocol: " + protocol
            
            if port == -1:
                port = 443 if protocol == 'https' else 80
            
            path = parsed_url['path'] if parsed_url['path'] else '/'
            if parsed_url['query']:
                path += '?' + parsed_url['query']
            
            request = method + " " + path + " HTTP/1.1\r\n"
            
            if 'Host' not in headers:
                headers['Host'] = host
            
            if data:
                headers['Content-Length'] = str(len(data))
            
            for key, value in headers.items():
                request += key + ": " + value + "\r\n"
            
            request += "\r\n"
            
            if data:
                request += data
            
            return request, None
        
        except Exception as e:
            return None, "Error building request: " + str(e)
    
    def changedUpdate(self, e):
        self._convertCurl()
    
    def insertUpdate(self, e):
        self._convertCurl()
    
    def removeUpdate(self, e):
        self._convertCurl()
    
    def _convertCurl(self):
        curl_text = self.curl_input.getText().strip()
        
        if not curl_text:
            self.http_output.setText("")
            return
        
        parsed, error = self._parseCurl(curl_text)
        
        if error:
            self.http_output.setText("Error: " + error)
            return
        
        http_request, error = self._buildHttpRequest(parsed)
        
        if error:
            self.http_output.setText("Error: " + error)
            return
        
        self.http_output.setText(http_request)
    
    def _sendToRepeater(self, e):
        try:
            http_request_text = self.http_output.getText()
            
            if not http_request_text or http_request_text.startswith("Error"):
                return
            
            curl_text = self.curl_input.getText().strip()
            parsed, error = self._parseCurl(curl_text)
            
            if error or not parsed:
                return
            
            url = parsed['url']
            parsed_url = self._parseURL(url)
            
            if not parsed_url:
                return
            
            host = parsed_url['host']
            port = parsed_url['port']
            protocol = parsed_url['scheme'].lower()
            
            if port == -1:
                port = 443 if protocol == 'https' else 80
            
            use_https = protocol == 'https'
            
            request_bytes = http_request_text.encode('utf-8')
            
            self._callbacks.sendToRepeater(host, port, use_https, request_bytes, None)
        
        except Exception as e:
            self.http_output.setText("Error sending to Repeater: " + str(e))
    
    def _clear(self, e):
        self.curl_input.setText("")
        self.http_output.setText("")
    
    def getUiComponent(self):
        return self.panel
    
    def getTabCaption(self):
        return "Curl Converter"
    
    def isEnabled(self):
        return True