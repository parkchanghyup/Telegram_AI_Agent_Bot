document.addEventListener('DOMContentLoaded', () => {
    const userInput = document.getElementById('user-input');
    const sendBtn = document.getElementById('send-btn');
    const chatBox = document.getElementById('chat-box');
    const sidebar = document.getElementById('sidebar');
    const sidebarToggle = document.getElementById('sidebar-toggle');
    const sidebarOpen = document.getElementById('sidebar-open');
    const mcpServers = document.getElementById('mcp-servers');
    const refreshBtn = document.getElementById('refresh-config');
    const saveBtn = document.getElementById('save-config');

    let currentConfig = {};

    // Chat functionality
    const sendMessage = async () => {
        const messageText = userInput.value.trim();
        if (messageText === '') return;

        appendMessage('user-message', messageText);
        userInput.value = '';

        try {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: messageText }),
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const data = await response.json();
            appendMessage('bot-message', data.response);
        } catch (error) {
            console.error('Error:', error);
            appendMessage('bot-message', 'Sorry, something went wrong.');
        }
    };

    const appendMessage = (senderClass, text) => {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message', senderClass);
        messageElement.textContent = text;
        chatBox.appendChild(messageElement);
        chatBox.scrollTop = chatBox.scrollHeight;
    };

    // Sidebar functionality
    const toggleSidebar = () => {
        sidebar.classList.toggle('collapsed');
    };

    // MCP Configuration functionality
    const loadConfig = async () => {
        try {
            const response = await fetch('/api/config');
            const config = await response.json();
            currentConfig = config;
            displayMcpServers(config.mcpServers || {});
        } catch (error) {
            console.error('Error loading config:', error);
        }
    };

    const displayMcpServers = (servers) => {
        mcpServers.innerHTML = '';
        
        // Add server button
        const addButton = document.createElement('button');
        addButton.className = 'add-server';
        addButton.textContent = '+ Add New Server';
        addButton.addEventListener('click', () => addNewServer());
        mcpServers.appendChild(addButton);

        // Display existing servers
        Object.entries(servers).forEach(([name, config]) => {
            const serverElement = createServerElement(name, config);
            mcpServers.appendChild(serverElement);
        });
    };

    const createServerElement = (name, config) => {
        const serverDiv = document.createElement('div');
        serverDiv.className = 'server-item';
        serverDiv.innerHTML = `
            <div class="server-header">
                <div class="server-name">${name}</div>
                <div class="server-status inactive">Inactive</div>
            </div>
            <div class="server-details">
                <div class="server-field">
                    <label>Server Name</label>
                    <input type="text" class="server-name-input" value="${name}" data-original="${name}">
                </div>
                <div class="server-field">
                    <label>Command</label>
                    <input type="text" class="server-command" value="${config.command || ''}">
                </div>
                <div class="server-field">
                    <label>Arguments (one per line)</label>
                    <textarea class="server-args">${(config.args || []).join('\n')}</textarea>
                </div>
                <div class="server-actions">
                    <button class="btn-small btn-delete" onclick="deleteServer('${name}')">Delete</button>
                </div>
            </div>
        `;
        return serverDiv;
    };

    const addNewServer = () => {
        const name = prompt('Enter server name:');
        if (name && !currentConfig.mcpServers[name]) {
            currentConfig.mcpServers[name] = {
                command: 'python',
                args: []
            };
            displayMcpServers(currentConfig.mcpServers);
        }
    };

    window.deleteServer = (name) => {
        if (confirm(`Are you sure you want to delete server "${name}"?`)) {
            delete currentConfig.mcpServers[name];
            displayMcpServers(currentConfig.mcpServers);
        }
    };

    const saveConfig = async () => {
        try {
            // Collect current form data
            const servers = {};
            const serverItems = document.querySelectorAll('.server-item');
            
            serverItems.forEach(item => {
                const nameInput = item.querySelector('.server-name-input');
                const commandInput = item.querySelector('.server-command');
                const argsTextarea = item.querySelector('.server-args');
                
                if (nameInput && commandInput && argsTextarea) {
                    const name = nameInput.value.trim();
                    const originalName = nameInput.dataset.original;
                    
                    if (name) {
                        servers[name] = {
                            command: commandInput.value.trim(),
                            args: argsTextarea.value.split('\n').filter(line => line.trim())
                        };
                        
                        // Handle name changes
                        if (originalName && originalName !== name && currentConfig.mcpServers[originalName]) {
                            delete currentConfig.mcpServers[originalName];
                        }
                    }
                }
            });

            currentConfig.mcpServers = servers;

            const response = await fetch('/api/config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(currentConfig),
            });

            const result = await response.json();
            if (result.success) {
                alert('Configuration saved successfully!');
                loadConfig(); // Reload to reflect changes
            } else {
                alert('Error saving configuration: ' + result.error);
            }
        } catch (error) {
            console.error('Error saving config:', error);
            alert('Error saving configuration');
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
    sidebarOpen.addEventListener('click', toggleSidebar);
    refreshBtn.addEventListener('click', loadConfig);
    saveBtn.addEventListener('click', saveConfig);

    // Initialize
    loadConfig();
});
