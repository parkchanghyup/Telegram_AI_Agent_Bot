document.addEventListener('DOMContentLoaded', () => {
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const chatBox = document.getElementById('chat-box');
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebarOpenBtn = document.getElementById('sidebar-open-btn');
    const mcpServers = document.getElementById('mcp-servers');
    const saveBtn = document.getElementById('save-config');
    const newChatBtn = document.getElementById('new-chat-btn');
    const mcpServersToggle = document.getElementById('mcp-servers-toggle');
    const openMcpToolsModalBtn = document.getElementById('open-mcp-tools-modal-btn');
    const mcpToolsContainer = document.getElementById('mcp-tools');
    const jsonImportTextarea = document.getElementById('json-import');
    const importJsonBtn = document.getElementById('import-json');

    // LLM Config Elements
    const openLlmModalBtn = document.getElementById('open-llm-modal-btn');
    const llmModalOverlay = document.getElementById('llm-modal-overlay');
    const llmModalClose = document.getElementById('llm-modal-close');
    const llmProviderSelect = document.getElementById('llm-provider');
    const modelNameInput = document.getElementById('model-name');
    const ollamaUrlInput = document.getElementById('ollama-url');
    const saveLlmConfigBtn = document.getElementById('save-llm-config');
    const ollamaUrlGroup = document.getElementById('ollama-url-group');

    // Environment Config Elements
    const openEnvModalBtn = document.getElementById('open-env-modal-btn');
    const envModalOverlay = document.getElementById('env-modal-overlay');
    const envModalClose = document.getElementById('env-modal-close');
    const envVariablesContainer = document.getElementById('env-variables-container');
    const addEnvBtn = document.getElementById('add-env-btn');
    const saveEnvConfigBtn = document.getElementById('save-env-config');

    // MCP Tools Modal Elements
    const mcpToolsModalOverlay = document.getElementById('mcp-tools-modal-overlay');
    const mcpToolsModalClose = document.getElementById('mcp-tools-modal-close');

    // Modal Elements
    const successModalOverlay = document.getElementById('success-modal-overlay');
    const modalMessageText = document.getElementById('modal-message-text');
    const modalCloseBtn = document.getElementById('modal-close-btn');



    let currentConfig = {};

    // Helper function to update collapsible section height
    const updateCollapsibleHeight = (sectionId) => {
        const content = document.getElementById(sectionId);
        if (content && content.classList.contains('expanded')) {
            // Use a timeout to allow the DOM to update before getting scrollHeight
            setTimeout(() => {
                // Reset max-height to get accurate scrollHeight
                content.style.maxHeight = 'none';
                const newHeight = content.scrollHeight;
                content.style.maxHeight = newHeight + "px";
            }, 10);
        }
    };

    // Chat functionality
    const sendMessage = async () => {
        const messageText = userInput.value.trim();
        if (messageText === '') return;

        appendMessage('user-message', messageText);
        userInput.value = '';
        
        // Show typing indicator
        const typingId = 'typing-' + Date.now();
        appendMessage('bot-message', '생각 중...', typingId);

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: messageText }),
            });

            // Remove typing indicator
            const typingElement = document.getElementById(typingId);
            if (typingElement) {
                typingElement.remove();
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const errorMessage = errorData.response || `HTTP ${response.status}: ${response.statusText}`;
                throw new Error(errorMessage);
            }

            const data = await response.json();
            appendMessage('bot-message', data.response);
            
            // Refresh tools after successful chat (in case MCP tools were used)
            // setTimeout(loadTools, 1000);
            
        } catch (error) {
            console.error('Chat Error:', error);
            // Remove typing indicator if still present
            const typingElement = document.getElementById(typingId);
            if (typingElement) {
                typingElement.remove();
            }
            
            let errorMessage = error.message;
            if (errorMessage.includes('503')) {
                errorMessage += ' - Try reinitializing the agent.';
            } else if (errorMessage.includes('500')) {
                errorMessage += ' - Server error occurred.';
            }
            
            appendMessage('bot-message', `❌ Error: ${errorMessage}`);
        }
    };

    const appendMessage = (senderClass, text, messageId = null) => {
        // Hide chat header when first real message is added (exclude typing indicators)
        const chatHeader = document.querySelector('.chat-header');
        const realMessages = chatBox.querySelectorAll('.message:not([id*="typing"])');
        if (chatHeader && realMessages.length === 0 && !messageId?.includes('typing')) {
            chatHeader.style.display = 'none';
        }

        const messageElement = document.createElement('div');
        messageElement.classList.add('message', senderClass);
        
        // For bot messages, create proper structure with emoji and content wrapper
        if (senderClass === 'bot-message') {
            // Create image element for bot icon
            const imgElement = document.createElement('img');
            imgElement.src = '/static/img.png';
            imgElement.alt = 'Bot Icon';
            imgElement.classList.add('bot-message-icon');

            // Create a wrapper for the icon
            const iconWrapper = document.createElement('div');
            iconWrapper.classList.add('bot-message-emoji');
            iconWrapper.appendChild(imgElement);

            // Create wrapper for content and copy button
            const messageWrapper = document.createElement('div');
            messageWrapper.classList.add('bot-message-wrapper');
            
            // Create content wrapper
            const contentWrapper = document.createElement('div');
            contentWrapper.classList.add('bot-message-content');
            
            // Convert markdown to HTML for bot messages
            if (window.marked) {
                try {
                    // Configure marked for security and better rendering
                    const renderer = new marked.Renderer();
                    
                    // Custom link renderer to open in new tab and add security
                    renderer.link = function(href, title, text) {
                        return `<a href="${href}" title="${title || ''}" target="_blank" rel="noopener noreferrer">${text}</a>`;
                    };
                    
                    marked.setOptions({
                        renderer: renderer,
                        breaks: true,
                        gfm: true,
                        sanitize: false,
                        smartLists: true,
                        smartypants: false
                    });
                    
                    contentWrapper.innerHTML = marked.parse(text);
                    
                    // Apply syntax highlighting to code blocks
                    if (window.hljs) {
                        contentWrapper.querySelectorAll('pre code').forEach((block) => {
                            hljs.highlightElement(block);
                        });
                    }
                } catch (error) {
                    console.error('Markdown parsing error:', error);
                    contentWrapper.textContent = text; // Fallback to plain text
                }
            } else {
                contentWrapper.textContent = text;
            }
            
            // Add copy button
            const copyButton = document.createElement('button');
            copyButton.classList.add('copy-btn');
            copyButton.innerHTML = '<i class="fas fa-copy"></i>Copy';
            copyButton.onclick = () => copyToClipboard(text, copyButton);
            
            // Assemble the structure
            messageWrapper.appendChild(contentWrapper);
            messageWrapper.appendChild(copyButton);
            messageElement.appendChild(iconWrapper); // Append the icon wrapper
            messageElement.appendChild(messageWrapper);
        } else {
            // For user messages, just set text content
            messageElement.textContent = text;
        }
        
        if (messageId) {
            messageElement.id = messageId;
        }
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
    };
    
    // Copy to clipboard function
    const copyToClipboard = async (text, buttonElement) => {
        try {
            await navigator.clipboard.writeText(text);
            
            // Update button to show success
            const originalHTML = buttonElement.innerHTML;
            buttonElement.innerHTML = '<i class="fas fa-check"></i>Copied!';
            buttonElement.classList.add('copied');
            
            // Reset button after 2 seconds
            setTimeout(() => {
                buttonElement.innerHTML = originalHTML;
                buttonElement.classList.remove('copied');
            }, 2000);
        } catch (err) {
            console.error('Failed to copy text: ', err);
            
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            try {
                document.execCommand('copy');
                
                // Update button to show success
                const originalHTML = buttonElement.innerHTML;
                buttonElement.innerHTML = '<i class="fas fa-check"></i>Copied!';
                buttonElement.classList.add('copied');
                
                setTimeout(() => {
                    buttonElement.innerHTML = originalHTML;
                    buttonElement.classList.remove('copied');
                }, 2000);
            } catch (fallbackErr) {
                console.error('Fallback copy failed: ', fallbackErr);
            }
            document.body.removeChild(textArea);
        }
    };

    // Sidebar functionality
    const toggleSidebar = () => {
        sidebar.classList.toggle('collapsed');
    };

    // New chat functionality
    const clearChat = () => {
        chatBox.innerHTML = '';
        userInput.value = '';
        // Show chat header when chat is cleared
        const chatHeader = document.querySelector('.chat-header');
        if (chatHeader) {
            chatHeader.style.display = 'flex';
        }
    };

    // Success Modal functionality
    const showSuccessModal = (message) => {
        modalMessageText.textContent = message;
        successModalOverlay.classList.add('show');
        
        // Prevent body scroll when modal is open
        document.body.style.overflow = 'hidden';
    };

    const hideSuccessModal = () => {
        successModalOverlay.classList.remove('show');
        
        // Restore body scroll
        document.body.style.overflow = '';
    };

    // LLM Modal functionality
    const showLlmModal = () => {
        llmModalOverlay.classList.add('show');
        document.body.style.overflow = 'hidden';
        loadLlmConfig();
    };

    const hideLlmModal = () => {
        llmModalOverlay.classList.remove('show');
        document.body.style.overflow = '';
    };

    // Environment Modal functionality
    const showEnvModal = () => {
        envModalOverlay.classList.add('show');
        document.body.style.overflow = 'hidden';
        
        // Load current environment variables
        loadEnvConfig();
    };

    const hideEnvModal = () => {
        envModalOverlay.classList.remove('show');
        document.body.style.overflow = '';
    };

    // MCP Tools Modal functionality
    const showMcpToolsModal = () => {
        mcpToolsModalOverlay.classList.add('show');
        document.body.style.overflow = 'hidden';
    };

    const hideMcpToolsModal = () => {
        mcpToolsModalOverlay.classList.remove('show');
        document.body.style.overflow = '';
    };

    // Environment Configuration functionality
    let envVariableCount = 0;

    const escapeHTML = (str) => {
        return str.replace(/"/g, '&quot;');
    };

    const createEnvVariableRow = (key = '', value = '') => {
        const rowId = `env-row-${envVariableCount++}`;
        const rowDiv = document.createElement('div');
        rowDiv.className = 'env-variable-row';
        rowDiv.id = rowId;
        
        rowDiv.innerHTML = `
            <div class="env-inputs">
                <input type="text" class="env-key" placeholder="새 변수 이름" value="${escapeHTML(key)}">
                <input type="text" class="env-value" placeholder="값" value="${escapeHTML(value)}">
                <button class="btn-delete-env" onclick="removeEnvVariable('${rowId}')" title="Delete variable">
                    ×
                </button>
            </div>
        `;
        
        return rowDiv;
    };

    const addEnvVariable = (key = '', value = '') => {
        const rowElement = createEnvVariableRow(key, value);
        envVariablesContainer.appendChild(rowElement);
    };

    window.removeEnvVariable = (rowId) => {
        const rowElement = document.getElementById(rowId);
        if (rowElement) {
            rowElement.remove();
        }
    };

    const parseEnvContent = (content) => {
        const variables = [];
        const lines = content.split('\n');
        
        for (const line of lines) {
            const trimmedLine = line.trim();
            // Skip empty lines and comments
            if (trimmedLine && !trimmedLine.startsWith('#')) {
                const equalIndex = trimmedLine.indexOf('=');
                if (equalIndex > 0) {
                    const key = trimmedLine.substring(0, equalIndex).trim();
                    let value = trimmedLine.substring(equalIndex + 1).trim();
                    // Strip quotes if they exist at both ends
                    if ((value.startsWith('"') && value.endsWith('"')) || (value.startsWith("'") && value.endsWith("'"))) {
                        value = value.substring(1, value.length - 1);
                    }
                    variables.push({ key, value });
                }
            }
        }
        
        return variables;
    };

    const loadEnvConfig = async () => {
        try {
            const response = await fetch('/api/env');
            const envData = await response.json();
            
            // Clear existing variables
            envVariablesContainer.innerHTML = '';
            envVariableCount = 0;
            
            if (envData.content) {
                const variables = parseEnvContent(envData.content);
                variables.forEach(({ key, value }) => addEnvVariable(key, value));
            }
            
            // Add at least one empty row if no variables exist
            if (envVariablesContainer.children.length === 0) {
                addEnvVariable();
            }
            
        } catch (error) {
            console.error('Error loading env config:', error);
            // Add an empty row on error
            addEnvVariable();
        }
    };

    const saveEnvConfig = async () => {
        const envRows = envVariablesContainer.querySelectorAll('.env-variable-row');
        const envLines = [];
        
        envRows.forEach(row => {
            const keyInput = row.querySelector('.env-key');
            const valueInput = row.querySelector('.env-value');
            const key = keyInput.value.trim();
            const value = valueInput.value.trim();
            
            if (key && value) {
                envLines.push(`${key}=${value}`);
            }
        });
        
        const content = envLines.join('\n');

        try {
            const response = await fetch('/api/env', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ content })
            });

            const result = await response.json();
            if (result.success) {
                showSuccessModal('✅ .env 파일이 저장되었습니다.');
                hideEnvModal(); // Close the env modal after successful save
            } else {
                alert('Error saving .env file: ' + result.error);
            }
        } catch (error) {
            console.error('Error saving env config:', error);
            alert('Error saving .env file.');
        }
    };

    // LLM Configuration functionality
    const loadLlmConfig = async () => {
        try {
            const response = await fetch('/api/llm_config');
            const llmConfig = await response.json();
            
            llmProviderSelect.value = llmConfig.llm_provider || 'openai';
            modelNameInput.value = llmConfig.model_name || '';
            ollamaUrlInput.value = llmConfig.ollama_base_url || 'http://localhost:11434/v1';

            toggleLlmFields();
        } catch (error) {
            console.error('Error loading LLM config:', error);
        }
    };

    const toggleLlmFields = () => {
        const provider = llmProviderSelect.value;
        if (provider === 'ollama') {
            ollamaUrlGroup.style.display = 'block';
        } else {
            ollamaUrlGroup.style.display = 'none';
        }
    };

    const saveLlmConfig = async () => {
        const newLlmConfig = {
            llm_provider: llmProviderSelect.value,
            model_name: modelNameInput.value.trim(),
            ollama_base_url: ollamaUrlInput.value.trim()
        };

        if (!newLlmConfig.model_name) {
            alert('Model Name is required.');
            return;
        }

        try {
            const response = await fetch('/api/llm_config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(newLlmConfig)
            });

            const result = await response.json();
            if (result.success) {
                hideLlmModal(); // Close LLM modal first
                showSuccessModal('✅ LLM 설정이 저장되었습니다. 에이전트를 초기화하는 중...');
                
                // Reinitialize agent
                reinitializeApp();
            } else {
                alert('Error saving LLM configuration: ' + result.error);
            }
        } catch (error) {
            console.error('Error saving LLM config:', error);
            alert('Error saving LLM configuration.');
        }
    };

    // Function to reinitialize the agent and update UI
    const reinitializeApp = async () => {
        try {
            const initResponse = await fetch('/api/init', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
            const initResult = await initResponse.json();
            
            if (initResult.success) {
                showSuccessModal('🎉 에이전트 초기화가 완료되었습니다!');
                // Refresh config, tools, and server status
                loadConfig();
                loadLlmConfig();
                loadTools();
                loadServerStatus();
                setTimeout(() => {
                    updateCollapsibleHeight('mcp-servers');
                    updateCollapsibleHeight('mcp-tools');
                }, 100);
            } else {
                appendMessage('bot-message', `⚠️ 에이전트 초기화 실패: ${initResult.error || 'Unknown error'}`);
            }
        } catch (initError) {
            console.error('Agent initialization error:', initError);
            appendMessage('bot-message', `⚠️ 에이전트 초기화 중 오류 발생: ${initError.message}`);
        }
    };


    // MCP Configuration functionality
    const loadConfig = async () => {
        try {
            const response = await fetch('/api/config');
            const config = await response.json();
            currentConfig = config;
            
            // 초기에는 기존 방식으로 모든 서버 표시
            displayMcpServers(config.mcpServers || []);
            
            // 서버 상태는 별도로 로드 (이때 Active/Inactive 분리됨)
            setTimeout(loadServerStatus, 100);
        } catch (error) {
            console.error('Error loading config:', error);
        }
    };

    const displayMcpServers = (servers, activeServerNames = []) => {
        const serverListItems = document.getElementById('server-list-items');
        serverListItems.innerHTML = '';

        // activeServerNames가 제공된 경우, 해당 서버들만 표시
        if (activeServerNames.length > 0) {
            const activeServers = servers.filter(server => 
                activeServerNames.includes(server.name)
            );
            
            activeServers.forEach((serverConfig, index) => {
                const name = serverConfig.name || `Server-${index + 1}`;
                const serverElement = createServerElement(name, serverConfig, index);
                serverListItems.appendChild(serverElement);
            });
        } else {
            // 기존 동작: 모든 서버 표시 (하위 호환성 유지)
            servers.forEach((serverConfig, index) => {
                const name = serverConfig.name || `Server-${index + 1}`;
                const serverElement = createServerElement(name, serverConfig, index);
                serverListItems.appendChild(serverElement);
            });
        }

        // Update collapsible section height after adding servers
        updateCollapsibleHeight('mcp-servers');
    };

    const createServerElement = (name, config, index) => {
        const serverDiv = document.createElement('div');
        serverDiv.className = 'server-item-simple';
        serverDiv.innerHTML = `
            <div class="server-item-content">
                <span class="server-name-simple">${name}</span>
                <button class="btn-delete-simple" onclick="deleteServer(${index})" title="Delete ${name}">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        `;
        return serverDiv;
    };



    window.deleteServer = (index) => {
        const serverName = currentConfig.mcpServers[index]?.name || `Server-${index + 1}`;
        if (confirm(`Are you sure you want to delete server "${serverName}"?`)) {
            currentConfig.mcpServers.splice(index, 1);
            
            // Active Servers 즉시 업데이트
            displayMcpServers(currentConfig.mcpServers);
            
            // Inactive Servers도 즉시 업데이트 (백엔드 호출 없이 직접 필터링)
            updateInactiveServersAfterDeletion(serverName);
            
            // Update height after server deletion
            setTimeout(() => updateCollapsibleHeight('mcp-servers'), 50);
        }
    };

    // 삭제된 서버를 Inactive Servers에서도 제거하는 함수
    const updateInactiveServersAfterDeletion = (deletedServerName) => {
        const inactiveContainer = document.getElementById('inactive-server-list-items');
        const inactiveItems = inactiveContainer.querySelectorAll('.server-item-simple.inactive');
        
        inactiveItems.forEach(item => {
            const serverNameElement = item.querySelector('.server-name-simple');
            if (serverNameElement && serverNameElement.textContent.includes(deletedServerName)) {
                item.remove();
            }
        });
        
        // 만약 모든 inactive 서버가 삭제되었다면 기본 메시지 표시
        if (inactiveContainer.children.length === 0) {
            const noServersElement = document.createElement('div');
            noServersElement.className = 'server-item-simple inactive';
            noServersElement.innerHTML = `
                <div class="server-item-content">
                    <span class="server-name-simple">✅ 모든 서버가 정상 작동중입니다</span>
                </div>
            `;
            inactiveContainer.appendChild(noServersElement);
        }
    };

    const importJson = () => {
        const jsonText = jsonImportTextarea.value.trim();
        if (!jsonText) {
            alert('Please paste JSON configuration first.');
            return;
        }

        try {
            const importedData = JSON.parse(jsonText);
            
            // Support both new array format and old object format for backward compatibility
            let serversToImport = [];
            
            if (Array.isArray(importedData)) {
                // New format: direct array of servers
                serversToImport = importedData;
            } else if (typeof importedData === 'object' && importedData !== null) {
                if (importedData.mcpServers && Array.isArray(importedData.mcpServers)) {
                    // New format: wrapped in mcpServers array
                    serversToImport = importedData.mcpServers;
                } else if (importedData.mcpServers && typeof importedData.mcpServers === 'object') {
                    // Smithery format: mcpServers is an object with server names as keys
                    serversToImport = Object.entries(importedData.mcpServers).map(([name, config]) => {
                        // Ensure config is an object, not a string
                        if (typeof config === 'object' && config !== null) {
                            return {
                                name: name,
                                ...config
                            };
                        } else {
                            // If config is a string or primitive, treat it as URL
                            return {
                                name: name,
                                url: String(config)
                            };
                        }
                    });
                } else if (importedData.name && (importedData.url || importedData.command)) {
                    // Single server object format
                    serversToImport = [importedData];
                } else {
                    // Old format: object with server names as keys (direct at root level)
                    serversToImport = Object.entries(importedData).map(([name, config]) => {
                        // Ensure config is an object, not a string
                        if (typeof config === 'object' && config !== null) {
                            return {
                                name: name,
                                ...config
                            };
                        } else {
                            // If config is a string or primitive, treat it as URL
                            return {
                                name: name,
                                url: String(config)
                            };
                        }
                    });
                }
            } else {
                throw new Error('JSON must be an array or object');
            }

            // Initialize mcpServers if not exists
            if (!currentConfig.mcpServers) {
                currentConfig.mcpServers = [];
            }

            let importedCount = 0;
            for (const serverConfig of serversToImport) {
                if (typeof serverConfig === 'object' && serverConfig !== null && serverConfig.name) {
                    // Check if server already exists
                    const existingIndex = currentConfig.mcpServers.findIndex(s => s.name === serverConfig.name);
                    
                    if (existingIndex >= 0) {
                        if (confirm(`Server "${serverConfig.name}" already exists. Do you want to overwrite it?`)) {
                            currentConfig.mcpServers[existingIndex] = serverConfig;
                            importedCount++;
                        }
                    } else {
                        currentConfig.mcpServers.push(serverConfig);
                        importedCount++;
                    }
                }
            }

            if (importedCount > 0) {
                displayMcpServers(currentConfig.mcpServers);
                jsonImportTextarea.value = '';
                // Update height after importing servers
                setTimeout(() => updateCollapsibleHeight('mcp-servers'), 50);
                alert(`Successfully imported ${importedCount} server(s). Don't forget to save your changes!`);
            } else {
                alert('No valid server configurations found in the JSON.');
            }

        } catch (error) {
            alert(`Invalid JSON format: ${error.message}`);
        }
    };

    const saveConfig = async () => {
        try {
            // Validate and clean the configuration before saving
            const cleanConfig = {
                mcpServers: (currentConfig.mcpServers || []).filter(server => {
                    // Only include valid server configurations
                    return server && 
                           typeof server === 'object' && 
                           server.name && 
                           typeof server.name === 'string' &&
                           (server.url || server.command);
                })
            };

            console.log('Original currentConfig:', currentConfig);
            console.log('Saving clean config:', cleanConfig);
            console.log('Clean config JSON:', JSON.stringify(cleanConfig, null, 2));

            const response = await fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(cleanConfig),
            });

            const result = await response.json();
            if (result.success) {
                // Show initial success message
                showSuccessModal('✅ 설정이 저장되었습니다. 에이전트를 초기화하는 중...');
                
                // Reinitialize agent after successful save
                reinitializeApp();

            } else {
                alert('Error saving configuration: ' + result.error);
            }
        } catch (error) {
            console.error('Error saving config:', error);
            alert('Error saving configuration');
        }
    };

    // MCP Tool functionality
    const loadTools = async () => {
        try {
            const response = await fetch('/api/tools');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const tools = await response.json();
            displayMcpTools(tools);
        } catch (error) {
            console.error('Error loading tools:', error);
            mcpToolsContainer.innerHTML = `<div class="tool-item"><span class="tool-description error">Failed to load tools. See console for details.</span></div>`;
            updateCollapsibleHeight('mcp-tools');
        }
    };

    const displayMcpTools = (toolsByServer) => {
        mcpToolsContainer.innerHTML = '';
        
        if (!toolsByServer || Object.keys(toolsByServer).length === 0) {
            mcpToolsContainer.innerHTML = '<div class="tool-item"><span class="tool-description">No tools found. Please configure MCP servers and initialize the agent.</span></div>';
            return;
        }
        
        // Check if toolsByServer is the old format (array) or new format (object)
        if (Array.isArray(toolsByServer)) {
            // Old format compatibility
            toolsByServer.forEach(tool => {
                const toolElement = document.createElement('div');
                toolElement.className = 'tool-item';
                toolElement.innerHTML = `
                    <span class="tool-name">${tool.name}</span>
                `;
                mcpToolsContainer.appendChild(toolElement);
            });
        } else {
            // New format: grouped by server
            Object.entries(toolsByServer).forEach(([serverName, tools]) => {
                // Create server group header
                const serverHeader = document.createElement('div');
                serverHeader.className = 'server-group-header';
                serverHeader.innerHTML = `
                    <i class="fas fa-server"></i>
                    <span>${serverName}</span>
                `;
                mcpToolsContainer.appendChild(serverHeader);
                
                // Create tools for this server
                tools.forEach(tool => {
                    const toolElement = document.createElement('div');
                    toolElement.className = 'tool-item';
                    toolElement.innerHTML = `
                        <div class="tool-content">
                            <span class="tool-name">${tool.name}</span>
                            ${tool.description ? `<span class="tool-description">${tool.description}</span>` : ''}
                        </div>
                    `;
                    mcpToolsContainer.appendChild(toolElement);
                });
            });
        }

        // Update collapsible section height after adding tools
        updateCollapsibleHeight('mcp-tools');
    };

    // Server Status functionality
    const loadServerStatus = async () => {
        try {
            const response = await fetch('/api/server-status');
            const serverStatus = await response.json();
            displayServerStatus(serverStatus);
        } catch (error) {
            console.error('Error loading server status:', error);
            // 에러가 발생하면 기본 메시지 표시
            displayServerStatus({
                active_servers: [],
                inactive_servers: [],
                message: 'Failed to load server status'
            });
        }
    };

    const displayServerStatus = (serverStatus) => {
        const activeContainer = document.getElementById('server-list-items');
        const inactiveContainer = document.getElementById('inactive-server-list-items');
        
        // Active servers 표시: 기존 config와 active server 이름을 결합하여 표시
        if (serverStatus.active_servers && serverStatus.active_servers.length > 0) {
            const activeServerNames = serverStatus.active_servers.map(server => server.name);
            displayMcpServers(currentConfig.mcpServers || [], activeServerNames);
        } else {
            // Active 서버가 없을 때
            activeContainer.innerHTML = `
                <div class="server-item-simple">
                    <div class="server-item-content">
                        <span class="server-name-simple">⚠️ 활성화된 서버가 없습니다</span>
                    </div>
                </div>
            `;
        }
        
        // Inactive servers 표시
        inactiveContainer.innerHTML = '';
        
        if (serverStatus.inactive_servers && serverStatus.inactive_servers.length > 0) {
            serverStatus.inactive_servers.forEach((server, index) => {
                const serverElement = createInactiveServerElement(server, index);
                inactiveContainer.appendChild(serverElement);
            });
        } else {
            // 비활성 서버가 없을 때
            const noServersElement = document.createElement('div');
            noServersElement.className = 'server-item-simple inactive';
            noServersElement.innerHTML = `
                <div class="server-item-content">
                    <span class="server-name-simple">✅ 모든 서버가 정상 작동중입니다</span>
                </div>
            `;
            inactiveContainer.appendChild(noServersElement);
        }

        // Update collapsible section height after adding servers
        updateCollapsibleHeight('mcp-servers');
    };

    const createInactiveServerElement = (server, index) => {
        const serverDiv = document.createElement('div');
        serverDiv.className = 'server-item-simple inactive';
        
        // 실제 config에서 해당 서버의 인덱스 찾기
        const actualIndex = currentConfig.mcpServers ? 
            currentConfig.mcpServers.findIndex(s => s.name === server.name) : -1;
        
        const errorMessage = server.error || 'Unknown error';
        
        serverDiv.innerHTML = `
            <div class="server-item-content inactive-content">
                <div class="server-line">
                    <span class="server-name-simple">❌ ${server.name}</span>
                    ${actualIndex >= 0 ? 
                        `<button class="btn-delete-simple" onclick="deleteServer(${actualIndex})" title="Delete ${server.name}">
                            <i class="fas fa-trash"></i>
                        </button>` : ''
                    }
                </div>
                <div class="server-error-line">
                    ${errorMessage}
                </div>
            </div>
        `;
        return serverDiv;
    };



    // Event listeners
    sendBtn.addEventListener('click', sendMessage);
    userInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
    sidebarToggle.addEventListener('click', toggleSidebar);
    sidebarOpenBtn.addEventListener('click', toggleSidebar);
    newChatBtn.addEventListener('click', clearChat);
    saveBtn.addEventListener('click', saveConfig);
    importJsonBtn.addEventListener('click', importJson);
    llmProviderSelect.addEventListener('change', toggleLlmFields);
    saveLlmConfigBtn.addEventListener('click', saveLlmConfig);
    
    // LLM Modal event listeners
    openLlmModalBtn.addEventListener('click', showLlmModal);
    llmModalClose.addEventListener('click', hideLlmModal);
    llmModalOverlay.addEventListener('click', (e) => {
        if (e.target === llmModalOverlay) {
            hideLlmModal();
        }
    });

    // MCP Tools Modal event listeners
    openMcpToolsModalBtn.addEventListener('click', showMcpToolsModal);
    mcpToolsModalClose.addEventListener('click', hideMcpToolsModal);
    mcpToolsModalOverlay.addEventListener('click', (e) => {
        if (e.target === mcpToolsModalOverlay) {
            hideMcpToolsModal();
        }
    });

    // Environment Modal event listeners
    openEnvModalBtn.addEventListener('click', showEnvModal);
    envModalClose.addEventListener('click', hideEnvModal);
    addEnvBtn.addEventListener('click', () => {
        addEnvVariable();
    });
    saveEnvConfigBtn.addEventListener('click', saveEnvConfig);
    
    // Success Modal event listeners
    modalCloseBtn.addEventListener('click', hideSuccessModal);
    successModalOverlay.addEventListener('click', (e) => {
        if (e.target === successModalOverlay) {
            hideSuccessModal();
        }
    });
    
    // Environment Modal event listeners
    envModalOverlay.addEventListener('click', (e) => {
        if (e.target === envModalOverlay) {
            hideEnvModal();
        }
    });
    
    // ESC key to close modals
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (successModalOverlay.classList.contains('show')) {
                hideSuccessModal();
            } else if (envModalOverlay.classList.contains('show')) {
                hideEnvModal();
            } else if (llmModalOverlay.classList.contains('show')) {
                hideLlmModal();
            }
            else if (mcpToolsModalOverlay.classList.contains('show')) {
                hideMcpToolsModal();
            }
        }
    });



    mcpServersToggle.addEventListener('click', () => {
        const content = document.getElementById('mcp-servers');
        const icon = mcpServersToggle.querySelector('i');
        content.classList.toggle('expanded');
        if (content.classList.contains('expanded')) {
            icon.style.transform = 'rotate(180deg)';
            updateCollapsibleHeight('mcp-servers');
        } else {
            icon.style.transform = 'rotate(0deg)';
            content.style.maxHeight = null;
        }
    });



    // Initialize
    loadConfig();
    loadLlmConfig();
    loadTools();
    clearChat(); // Add this line to display the initial message
});
