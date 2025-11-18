document.addEventListener('DOMContentLoaded', () => {
    const summaryIds = {
        totalUsers: document.getElementById('totalUsers'),
        activePlayers: document.getElementById('activePlayers'),
        hiddenPlayers: document.getElementById('hiddenPlayers'),
        totalGooncoins: document.getElementById('totalGooncoins'),
        averageGooncoins: document.getElementById('averageGooncoins')
    };
    const adminSearchInput = document.getElementById('adminSearch');
    const recentUsersList = document.getElementById('recentUsersList');
    const adminMessage = document.getElementById('adminMessage');
    const adminTable = document.getElementById('adminUsersTable');
    const tableBody = adminTable ? adminTable.querySelector('tbody') : null;
    const refreshButtons = [
        document.getElementById('refreshAdminData'),
        document.getElementById('refreshAdminDataTop')
    ].filter(Boolean);
    
    const state = {
        users: [],
        filter: ''
    };
    
    const numberFormatter = new Intl.NumberFormat('cs-CZ');
    const dateFormatter = new Intl.DateTimeFormat('cs-CZ', {
        dateStyle: 'medium',
        timeStyle: 'short'
    });
    
    const formatNumber = (value) => numberFormatter.format(Number(value || 0));
    
    const formatDate = (value) => {
        if (!value) {
            return '—';
        }
        const normalized = value.includes('T') ? value : value.replace(' ', 'T');
        const date = new Date(normalized);
        if (Number.isNaN(date.getTime())) {
            return value;
        }
        return dateFormatter.format(date);
    };
    
    const setMessage = (text, tone = 'info') => {
        if (!adminMessage) return;
        adminMessage.textContent = text;
        adminMessage.classList.remove('error', 'success', 'info');
        adminMessage.classList.add(tone);
    };
    
    const updateSummary = (data) => {
        if (!summaryIds.totalUsers) {
            return;
        }
        summaryIds.totalUsers.textContent = formatNumber(data.total_users || 0);
        summaryIds.activePlayers.textContent = formatNumber(data.active_players || 0);
        summaryIds.hiddenPlayers.textContent = formatNumber(data.hidden_players || 0);
        summaryIds.totalGooncoins.textContent = formatNumber(data.total_gooncoins || 0);
        summaryIds.averageGooncoins.textContent = formatNumber(data.average_gooncoins || 0);
    };
    
    const renderRecentUsers = (recent) => {
        if (!recentUsersList) return;
        if (!recent || recent.length === 0) {
            recentUsersList.innerHTML = '<li>Žádní noví hráči.</li>';
            return;
        }
        recentUsersList.innerHTML = recent.map((user) => `
            <li>
                <strong>${user.username}</strong>
                <span>${formatDate(user.created_at)}</span>
            </li>
        `).join('');
    };
    
    const applyFilter = () => {
        if (!state.filter) {
            return state.users;
        }
        return state.users.filter((user) =>
            user.username.toLowerCase().includes(state.filter)
        );
    };
    
    const renderTable = (users) => {
        if (!tableBody) return;
        if (!users || users.length === 0) {
            tableBody.innerHTML = `
                <tr>
                    <td colspan="6">Žádní hráči neodpovídají filtru.</td>
                </tr>
            `;
            return;
        }
        tableBody.innerHTML = users.map((user) => {
            const roleBadge = user.is_admin
                ? '<span class="badge badge-admin">Admin</span>'
                : '<span class="badge badge-player">Hráč</span>';
            const visibilityBadge = user.hidden
                ? '<span class="badge badge-hidden">Skrytý</span>'
                : '<span class="badge badge-visible">Viditelný</span>';
            const actionLabel = user.hidden ? 'Zobrazit v leaderboardu' : 'Skrýt z leaderboardu';
            const nextState = user.hidden ? 'show' : 'hide';
            
            return `
                <tr>
                    <td>
                        <div class="user-cell">
                            <strong>${user.username}</strong>
                            <small>${formatDate(user.created_at)}</small>
                        </div>
                    </td>
                    <td>${formatNumber(user.gooncoins)}</td>
                    <td>${formatNumber(user.total_clicks)}</td>
                    <td>${roleBadge}</td>
                    <td>${visibilityBadge}</td>
                    <td>
                        <button class="btn-outline"
                                data-action="toggle-hidden"
                                data-user-id="${user.id}"
                                data-next-state="${nextState}">
                            ${actionLabel}
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    };
    
    const fetchOverview = async () => {
        setMessage('Načítám data...', 'info');
        try {
            const response = await fetch('/api/admin/overview');
            if (!response.ok) {
                const errorPayload = await response.json().catch(() => ({}));
                throw new Error(errorPayload.error || 'Nepodařilo se načíst data');
            }
            const data = await response.json();
            state.users = data.users || [];
            updateSummary(data);
            renderRecentUsers(data.recent_users || []);
            renderTable(applyFilter());
            setMessage('Data načtena.', 'success');
        } catch (error) {
            setMessage(error.message, 'error');
        }
    };
    
    const toggleLeaderboardVisibility = async (userId, hide) => {
        setMessage('Ukládám změnu...', 'info');
        try {
            const response = await fetch(`/api/admin/users/${userId}/leaderboard`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ hide })
            });
            if (!response.ok) {
                const errorPayload = await response.json().catch(() => ({}));
                throw new Error(errorPayload.error || 'Změnu se nepodařilo uložit');
            }
            await response.json();
            await fetchOverview();
            setMessage('Změna byla uložena.', 'success');
        } catch (error) {
            setMessage(error.message, 'error');
        }
    };
    
    if (adminSearchInput) {
        adminSearchInput.addEventListener('input', (event) => {
            state.filter = event.target.value.trim().toLowerCase();
            renderTable(applyFilter());
        });
    }
    
    refreshButtons.forEach((button) => {
        button.addEventListener('click', fetchOverview);
    });
    
    if (tableBody) {
        tableBody.addEventListener('click', (event) => {
            const button = event.target.closest('[data-action="toggle-hidden"]');
            if (!button) {
                return;
            }
            const userId = Number(button.dataset.userId);
            const nextState = button.dataset.nextState;
            const hide = nextState === 'hide';
            button.disabled = true;
            toggleLeaderboardVisibility(userId, hide).finally(() => {
                button.disabled = false;
            });
        });
    }
    
    fetchOverview();
});

