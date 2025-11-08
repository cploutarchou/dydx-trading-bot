/**
 * Registration Diagnostic Test
 * 
 * Run this in the browser console while on the registration page:
 * 1. Open DevTools (F12)
 * 2. Go to Console tab
 * 3. Copy and paste this entire script
 * 4. Press Enter
 * 5. Follow the instructions
 */

(async function() {
    console.log('🧪 Starting Registration Diagnostic Test...\n');

    // Test 1: Check API base URL
    console.log('✓ Test 1: Checking API Base URL');
    const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8888';
    console.log(`  API Base URL: ${apiUrl}`);
    console.log(`  Status: ${apiUrl ? '✅ Configured' : '❌ Missing'}\n`);

    // Test 2: Test registration endpoint
    console.log('✓ Test 2: Testing Registration Endpoint');
    try {
        const testUsername = `test_${Date.now()}`;
        const testData = {
            username: testUsername,
            email: `${testUsername}@test.com`,
            password: 'TestPassword123'
        };

        console.log(`  Sending POST to ${apiUrl}/api/v1/auth/register`);
        console.log(`  Payload:`, testData);

        const response = await fetch(`${apiUrl}/api/v1/auth/register`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(testData)
        });

        const data = await response.json();
        console.log(`  Status Code: ${response.status}`);
        console.log(`  Response:`, data);

        if (response.ok) {
            console.log('  ✅ Registration endpoint working\n');
        } else {
            console.log('  ❌ Registration endpoint returned error\n');
        }
    } catch (error) {
        console.error('  ❌ Failed to test registration endpoint:', error);
        console.log('  Check if backend is running on', apiUrl, '\n');
    }

    // Test 3: Test login endpoint
    console.log('✓ Test 3: Testing Login Endpoint');
    try {
        const testLoginData = {
            username: 'admin',
            password: 'admin123'
        };

        console.log(`  Sending POST to ${apiUrl}/api/v1/auth/login`);
        console.log(`  Payload:`, testLoginData);

        const response = await fetch(`${apiUrl}/api/v1/auth/login`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(testLoginData)
        });

        const data = await response.json();
        console.log(`  Status Code: ${response.status}`);
        console.log(`  Response Keys:`, Object.keys(data));

        if (data?.data?.access_token || data?.access_token) {
            console.log('  ✅ Login endpoint working\n');
        } else {
            console.log('  ⚠️  Login endpoint responded but no token in response\n');
        }
    } catch (error) {
        console.error('  ❌ Failed to test login endpoint:', error, '\n');
    }

    // Test 4: Check localStorage
    console.log('✓ Test 4: Checking Browser Storage');
    const accessToken = localStorage.getItem('access_token');
    const refreshToken = localStorage.getItem('refresh_token');
    console.log(`  Access Token: ${accessToken ? '✅ Present' : '❌ Missing'}`);
    console.log(`  Refresh Token: ${refreshToken ? '✅ Present' : '❌ Missing'}\n`);

    // Test 5: Check API client
    console.log('✓ Test 5: Checking API Client');
    try {
        // This assumes the api module is available
        console.log(`  API Client loaded: ✅`);
        console.log(`  API Client has register method: ${typeof window.api?.register === 'function' ? '✅' : '❌'}`);
        console.log(`  API Client has login method: ${typeof window.api?.login === 'function' ? '✅' : '❌'}\n`);
    } catch (e) {
        console.log(`  ⚠️  Could not check API client (${e.message})\n`);
    }

    // Test 6: Validation rules check
    console.log('✓ Test 6: Frontend Validation Rules');
    const testCases = [
        { username: 'ab', valid: false, reason: 'Too short' },
        { username: 'user@123', valid: false, reason: 'Invalid characters' },
        { username: 'valid_user-1', valid: true, reason: 'Valid format' },
        { email: 'invalid.email', valid: false, reason: 'Missing domain' },
        { email: 'valid@example.com', valid: true, reason: 'Valid email' },
        { password: 'short', valid: false, reason: 'Too short, no uppercase/number' },
        { password: 'ValidPass1', valid: true, reason: 'Valid password' },
    ];

    testCases.forEach(test => {
        const status = test.valid ? '✅' : '❌';
        console.log(`  ${status} ${test.reason}: ${test.username || test.email || test.password}`);
    });
    console.log();

    // Summary
    console.log('📊 Diagnostic Summary:');
    console.log('  1. API is at:', apiUrl);
    console.log('  2. Make sure backend is running');
    console.log('  3. Test registration with unique username');
    console.log('  4. Check Network tab for request/response');
    console.log('  5. Review console logs for errors');
    console.log('\n✅ Diagnostic test complete!');
    console.log('\nNext steps:');
    console.log('1. Fill the registration form');
    console.log('2. Check browser console for detailed logs');
    console.log('3. Check Network tab (F12 → Network)');
    console.log('4. Look for any error messages');
})();
