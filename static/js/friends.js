// ========== FRIENDS SYSTEM ==========

async function loadFriends() {
    try {
        const response = await fetch('/api/friends');
        const data = await response.json();
        
        if (data.success) {
            // Render friends list
            const friendsListEl = document.getElementById('friendsList');
            if (friendsListEl) {
                if (data.friends && data.friends.length > 0) {
                    friendsListEl.innerHTML = data.friends.map(friend => `
                        <div class="friend-item">
                            <span class="friend-username">${escapeHtml(friend.username)}</span>
                            <button class="btn-friend-remove" onclick="removeFriend(${friend.friend_id})">Odstranit</button>
                        </div>
                    `).join('');
                } else {
                    friendsListEl.innerHTML = '<p class="muted">Zatím nemáš žádné přátele</p>';
                }
            }
            
            // Update friends count
            const friendsCountEl = document.getElementById('friendsCount');
            if (friendsCountEl) {
                const count = data.friends ? data.friends.length : 0;
                friendsCountEl.textContent = `${count} ${count === 1 ? 'přítel' : count < 5 ? 'přátelé' : 'přátel'}`;
            }
            
            // Render pending incoming requests
            const pendingIncomingEl = document.getElementById('pendingIncomingList');
            if (pendingIncomingEl) {
                if (data.pending_incoming && data.pending_incoming.length > 0) {
                    pendingIncomingEl.innerHTML = data.pending_incoming.map(req => `
                        <div class="friend-item">
                            <span class="friend-username">${escapeHtml(req.username)}</span>
                            <div class="friend-actions">
                                <button class="btn-friend-accept" onclick="acceptFriendRequest(${req.id})">Přijmout</button>
                                <button class="btn-friend-reject" onclick="rejectFriendRequest(${req.id})">Odmítnout</button>
                            </div>
                        </div>
                    `).join('');
                } else {
                    pendingIncomingEl.innerHTML = '<p class="muted">Žádné příchozí žádosti</p>';
                }
            }
            
            // Update pending incoming count
            const pendingIncomingCountEl = document.getElementById('pendingIncomingCount');
            if (pendingIncomingCountEl) {
                const count = data.pending_incoming ? data.pending_incoming.length : 0;
                pendingIncomingCountEl.textContent = count > 0 ? `${count} ${count === 1 ? 'žádost' : count < 5 ? 'žádosti' : 'žádostí'}` : 'Žádné žádosti';
            }
            
            // Render pending outgoing requests
            const pendingOutgoingEl = document.getElementById('pendingOutgoingList');
            if (pendingOutgoingEl) {
                if (data.pending_outgoing && data.pending_outgoing.length > 0) {
                    pendingOutgoingEl.innerHTML = data.pending_outgoing.map(req => `
                        <div class="friend-item">
                            <span class="friend-username">${escapeHtml(req.username)}</span>
                            <button class="btn-friend-cancel" onclick="rejectFriendRequest(${req.id})">Zrušit</button>
                        </div>
                    `).join('');
                } else {
                    pendingOutgoingEl.innerHTML = '<p class="muted">Žádné odeslané žádosti</p>';
                }
            }
            
            // Update pending outgoing count
            const pendingOutgoingCountEl = document.getElementById('pendingOutgoingCount');
            if (pendingOutgoingCountEl) {
                const count = data.pending_outgoing ? data.pending_outgoing.length : 0;
                pendingOutgoingCountEl.textContent = count > 0 ? `${count} ${count === 1 ? 'žádost' : count < 5 ? 'žádosti' : 'žádostí'}` : 'Žádné žádosti';
            }
        }
    } catch (error) {
        console.error('Error loading friends:', error);
        const friendsListEl = document.getElementById('friendsList');
        if (friendsListEl) {
            friendsListEl.innerHTML = '<p class="muted">Chyba při načítání přátel</p>';
        }
    }
}

async function searchFriends() {
    const searchInput = document.getElementById('friendSearchInput');
    const resultsEl = document.getElementById('friendSearchResults');
    
    if (!searchInput || !resultsEl) return;
    
    const query = searchInput.value.trim();
    
    if (query.length < 2) {
        resultsEl.innerHTML = '';
        return;
    }
    
    try {
        const response = await fetch(`/api/friends/search?q=${encodeURIComponent(query)}`);
        const data = await response.json();
        
        if (data.success) {
            if (data.users && data.users.length > 0) {
                resultsEl.innerHTML = data.users.map(user => `
                    <div class="friend-search-item">
                        <span class="friend-username">${escapeHtml(user.username)}</span>
                        <button class="btn-friend-add" onclick="sendFriendRequest(${user.id})">Přidat</button>
                    </div>
                `).join('');
            } else {
                resultsEl.innerHTML = '<p class="muted">Žádní uživatelé nenalezeni</p>';
            }
        } else {
            resultsEl.innerHTML = '<p class="muted">Chyba při vyhledávání</p>';
        }
    } catch (error) {
        console.error('Error searching friends:', error);
        resultsEl.innerHTML = '<p class="muted">Chyba při vyhledávání</p>';
    }
}

async function sendFriendRequest(friendId) {
    try {
        const response = await fetch('/api/friends/request', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({friend_id: friendId})
        });
        const data = await response.json();
        
        if (data.success) {
            alert(data.message || 'Žádost o přátelství odeslána');
            // Clear search and reload friends
            const searchInput = document.getElementById('friendSearchInput');
            if (searchInput) searchInput.value = '';
            const resultsEl = document.getElementById('friendSearchResults');
            if (resultsEl) resultsEl.innerHTML = '';
            loadFriends();
        } else {
            alert(data.error || 'Chyba při odesílání žádosti');
        }
    } catch (error) {
        console.error('Error sending friend request:', error);
        alert('Chyba při odesílání žádosti');
    }
}

async function acceptFriendRequest(requestId) {
    try {
        const response = await fetch('/api/friends/accept', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({request_id: requestId})
        });
        const data = await response.json();
        
        if (data.success) {
            alert(data.message || 'Žádost přijata');
            loadFriends();
        } else {
            alert(data.error || 'Chyba při přijímání žádosti');
        }
    } catch (error) {
        console.error('Error accepting friend request:', error);
        alert('Chyba při přijímání žádosti');
    }
}

async function rejectFriendRequest(requestId) {
    if (!confirm('Opravdu chceš zamítnout/zrušit tuto žádost?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/friends/reject', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({request_id: requestId})
        });
        const data = await response.json();
        
        if (data.success) {
            alert(data.message || 'Žádost zamítnuta');
            loadFriends();
        } else {
            alert(data.error || 'Chyba při zamítání žádosti');
        }
    } catch (error) {
        console.error('Error rejecting friend request:', error);
        alert('Chyba při zamítání žádosti');
    }
}

async function removeFriend(friendId) {
    if (!confirm('Opravdu chceš odstranit tohoto přítele?')) {
        return;
    }
    
    try {
        const response = await fetch('/api/friends/remove', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({friend_id: friendId})
        });
        const data = await response.json();
        
        if (data.success) {
            alert(data.message || 'Přítel odstraněn');
            loadFriends();
        } else {
            alert(data.error || 'Chyba při odstraňování přítele');
        }
    } catch (error) {
        console.error('Error removing friend:', error);
        alert('Chyba při odstraňování přítele');
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Setup friends search on Enter key and button click
document.addEventListener('DOMContentLoaded', () => {
    const friendSearchInput = document.getElementById('friendSearchInput');
    const friendSearchBtn = document.getElementById('friendSearchBtn');
    
    if (friendSearchInput) {
        friendSearchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                searchFriends();
            }
        });
    }
    
    if (friendSearchBtn) {
        friendSearchBtn.addEventListener('click', searchFriends);
    }
});

