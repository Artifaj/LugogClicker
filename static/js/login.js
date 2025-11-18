document.addEventListener('DOMContentLoaded', function() {
    const loginForm = document.getElementById('loginForm');
    const registerForm = document.getElementById('registerForm');
    const loginBox = document.querySelector('.login-box');
    const registerBox = document.getElementById('registerBox');
    const registerLink = document.getElementById('registerLink');
    const loginLink = document.getElementById('loginLink');
    const errorMessage = document.getElementById('errorMessage');
    const regErrorMessage = document.getElementById('regErrorMessage');
    
    registerLink.addEventListener('click', function(e) {
        e.preventDefault();
        loginBox.style.display = 'none';
        registerBox.style.display = 'block';
    });
    
    loginLink.addEventListener('click', function(e) {
        e.preventDefault();
        registerBox.style.display = 'none';
        loginBox.style.display = 'block';
    });
    
    loginForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        errorMessage.classList.remove('show');
        
        const username = document.getElementById('username').value;
        const password = document.getElementById('password').value;
        
        try {
            const response = await fetch('/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            
            if (data.success) {
                window.location.href = '/game';
            } else {
                errorMessage.textContent = data.error || 'Chyba při přihlašování';
                errorMessage.classList.add('show');
            }
        } catch (error) {
            errorMessage.textContent = 'Chyba připojení k serveru';
            errorMessage.classList.add('show');
        }
    });
    
    registerForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        regErrorMessage.classList.remove('show');
        
        const username = document.getElementById('regUsername').value;
        const password = document.getElementById('regPassword').value;
        
        try {
            const response = await fetch('/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ username, password })
            });
            
            const data = await response.json();
            
            if (data.success) {
                window.location.href = '/game';
            } else {
                regErrorMessage.textContent = data.error || 'Chyba při registraci';
                regErrorMessage.classList.add('show');
            }
        } catch (error) {
            regErrorMessage.textContent = 'Chyba připojení k serveru';
            regErrorMessage.classList.add('show');
        }
    });
});

