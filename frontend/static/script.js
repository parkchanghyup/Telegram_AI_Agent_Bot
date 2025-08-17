document.addEventListener('DOMContentLoaded', () => {
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const chatBox = document.getElementById('chat-box');
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebarOpenBtn = document.getElementById('sidebar-open-btn');
    const mcpServers = document.getElementById('mcp-servers');
    const refreshBtn = document.getElementById('refresh-config');
    const saveBtn = document.getElementById('save-config');
    const newChatBtn = document.getElementById('new-chat-btn');
    const mcpServersToggle = document.getElementById('mcp-servers-toggle');
    const mcpToolsToggle = document.getElementById('mcp-tools-toggle');
    const mcpToolsContainer = document.getElementById('mcp-tools');
    const jsonImportTextarea = document.getElementById('json-import');
    const importJsonBtn = document.getElementById('import-json');

    let currentConfig = {};

    // Chat functionality
    const sendMessage = async () => {
        const messageText = userInput.value.trim();
        if (messageText === '') return;

        appendMessage('user-message', messageText);
        userInput.value = '';
        
        // Show typing indicator
        const typingId = 'typing-' + Date.now();
        appendMessage('bot-message', '🤖 생각 중...', typingId);

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
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', senderClass);
        messageElement.textContent = text;
        if (messageId) {
            messageElement.id = messageId;
        }
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
    };

    // Sidebar functionality
    const toggleSidebar = () => {
        sidebar.classList.toggle('collapsed');
    };

    // New chat functionality
    const clearChat = () => {
        chatBox.innerHTML = '';
        userInput.value = '';
        appendMessage('bot-message', '안녕하세요! 새로운 대화를 시작합니다. 무엇을 도와드릴까요?');
    };

    // Agent reinitialization
    const reinitializeAgent = async () => {
        try {
            appendMessage('bot-message', '🔄 에이전트를 다시 초기화하고 있습니다...');
            
            const response = await fetch('/api/init', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            const result = await response.json();
            
            if (result.success) {
                appendMessage('bot-message', '✅ 에이전트가 성공적으로 초기화되었습니다!');
                // Refresh tools and config after successful initialization
                setTimeout(() => {
                    loadConfig();
                    loadTools();
                }, 500);
            } else {
                appendMessage('bot-message', `❌ 초기화 실패: ${result.error || 'Unknown error'}`);
            }
        } catch (error) {
            console.error('Reinitialize error:', error);
            appendMessage('bot-message', `❌ 초기화 중 오류 발생: ${error.message}`);
        }
    };

    // MCP Configuration functionality
    const loadConfig = async () => {
        try {
            const response = await fetch('/api/config');
            const config = await response.json();
            currentConfig = config;
            displayMcpServers(config.mcpServers || []);
        } catch (error) {
            console.error('Error loading config:', error);
        }
    };

    const displayMcpServers = (servers) => {
        const serverListItems = document.getElementById('server-list-items');
        serverListItems.innerHTML = '';

        servers.forEach((serverConfig, index) => {
            const name = serverConfig.name || `Server-${index + 1}`;
            const serverElement = createServerElement(name, serverConfig, index);
            serverListItems.appendChild(serverElement);
        });

        // After populating, update max-height if the section is expanded
        const content = document.getElementById('mcp-servers');
        if (content.classList.contains('expanded')) {
            // Use a timeout to allow the DOM to update before getting scrollHeight
            setTimeout(() => {
                content.style.maxHeight = content.scrollHeight + "px";
            }, 0);
        }
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
            displayMcpServers(currentConfig.mcpServers);
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
                } else if (importedData.name && (importedData.url || importedData.command)) {
                    // Single server object format
                    serversToImport = [importedData];
                } else {
                    // Old format: object with server names as keys
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
                alert('Configuration saved successfully!');
                loadConfig();
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
            const tools = await response.json();
            displayMcpTools(tools);
        } catch (error) {
            console.error('Error loading tools:', error);
        }
    };

    const displayMcpTools = (toolsByServer) => {
        mcpToolsContainer.innerHTML = '';
        
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

        // After populating, update max-height if the section is expanded
        const content = document.getElementById('mcp-tools');
        if (content.classList.contains('expanded')) {
            setTimeout(() => {
                content.style.maxHeight = content.scrollHeight + "px";
            }, 0);
        }
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
    refreshBtn.addEventListener('click', loadConfig);
    saveBtn.addEventListener('click', saveConfig);
    importJsonBtn.addEventListener('click', importJson);
    
    // Add reinitialize agent button listener
    const reinitBtn = document.getElementById('reinit-agent');
    if (reinitBtn) {
        reinitBtn.addEventListener('click', reinitializeAgent);
    }

    mcpServersToggle.addEventListener('click', () => {
        const content = document.getElementById('mcp-servers');
        const icon = mcpServersToggle.querySelector('i');
        content.classList.toggle('expanded');
        if (content.classList.contains('expanded')) {
            icon.style.transform = 'rotate(180deg)';
            content.style.maxHeight = content.scrollHeight + "px";
        } else {
            icon.style.transform = 'rotate(0deg)';
            content.style.maxHeight = null;
        }
    });

    mcpToolsToggle.addEventListener('click', () => {
        const content = document.getElementById('mcp-tools');
        const icon = mcpToolsToggle.querySelector('i');
        content.classList.toggle('expanded');
        if (content.classList.contains('expanded')) {
            icon.style.transform = 'rotate(180deg)';
            content.style.maxHeight = content.scrollHeight + "px";
        } else {
            icon.style.transform = 'rotate(0deg)';
            content.style.maxHeight = null;
        }
    });

    // Initialize
    loadConfig();
    // loadTools();
    clearChat(); // Add this line to display the initial message
});
