/**
 * CampusGuard AI - Student Login Client Script
 * Handles UI micro-interactions, password visibility, and loading states.
 * NOTE: Authentication is strictly validated on the Flask server.
 */

document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('student-login-form');
    const registerInput = document.getElementById('register_number');
    const passwordInput = document.getElementById('password');
    const togglePasswordBtn = document.getElementById('toggle-password-btn');
    const submitBtn = document.getElementById('submit-btn');
    const fillDemoBtn = document.getElementById('fill-demo-btn');

    // 1. Password Visibility Toggle
    if (togglePasswordBtn && passwordInput) {
        togglePasswordBtn.addEventListener('click', (e) => {
            e.preventDefault();
            const isPassword = passwordInput.type === 'password';
            passwordInput.type = isPassword ? 'text' : 'password';
            togglePasswordBtn.setAttribute('aria-label', isPassword ? 'Hide password' : 'Show password');
            
            // Toggle eye icon SVG
            const eyeOpen = togglePasswordBtn.querySelector('.eye-open');
            const eyeClosed = togglePasswordBtn.querySelector('.eye-closed');
            if (eyeOpen && eyeClosed) {
                eyeOpen.style.display = isPassword ? 'none' : 'block';
                eyeClosed.style.display = isPassword ? 'block' : 'none';
            }
        });
    }

    // 2. Demo Credentials Quick Fill
    if (fillDemoBtn && registerInput && passwordInput) {
        fillDemoBtn.addEventListener('click', () => {
            registerInput.value = 'STU001';
            passwordInput.value = 'Student@123';
            registerInput.classList.add('highlight-filled');
            passwordInput.classList.add('highlight-filled');
            setTimeout(() => {
                registerInput.classList.remove('highlight-filled');
                passwordInput.classList.remove('highlight-filled');
            }, 600);
            passwordInput.focus();
        });
    }

    // 3. Form Submit Handling & Loading State
    if (loginForm && submitBtn) {
        loginForm.addEventListener('submit', (e) => {
            const regVal = registerInput.value.trim();
            const passVal = passwordInput.value.trim();

            if (!regVal || !passVal) {
                e.preventDefault();
                if (!regVal) registerInput.focus();
                else if (!passVal) passwordInput.focus();
                return;
            }

            // Visual loading state on button
            submitBtn.classList.add('is-loading');
            submitBtn.disabled = true;
            const btnText = submitBtn.querySelector('.btn-text');
            if (btnText) {
                btnText.textContent = 'Verifying Credentials...';
            }

            // Native form submission will continue to Flask POST /student/login
        });
    }
});
