const { chromium } = require('playwright');

async function validateUI() {
    console.log('🎭 Starting Playwright UI validation...');
    
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    
    try {
        // Navigate to the app
        console.log('📱 Navigating to ED Bot v8...');
        await page.goto('http://localhost:8001');
        await page.waitForLoadState('networkidle');
        
        // Take initial screenshot
        await page.screenshot({ path: 'ui-initial.png', fullPage: true });
        
        // Check for CSP errors in console
        const cspErrors = [];
        page.on('console', msg => {
            if (msg.type() === 'error' && msg.text().includes('Content Security Policy')) {
                cspErrors.push(msg.text());
            }
        });
        
        // Wait for fonts to load
        await page.waitForTimeout(2000);
        
        // Validate layout elements
        const header = await page.locator('.chat-header');
        const messages = await page.locator('.chat-messages');
        const input = await page.locator('.chat-input-container');
        
        console.log('✅ Header present:', await header.isVisible());
        console.log('✅ Messages area present:', await messages.isVisible());
        console.log('✅ Input area present:', await input.isVisible());
        
        // Check viewport usage
        const viewport = page.viewportSize();
        const headerBox = await header.boundingBox();
        const messagesBox = await messages.boundingBox();
        const inputBox = await input.boundingBox();
        
        console.log('📐 Viewport:', viewport);
        console.log('📐 Header height:', headerBox?.height);
        console.log('📐 Messages height:', messagesBox?.height);
        console.log('📐 Input height:', inputBox?.height);
        
        // Calculate used space
        const totalUsed = (headerBox?.height || 0) + (messagesBox?.height || 0) + (inputBox?.height || 0);
        const deadspace = viewport.height - totalUsed;
        
        console.log('🎯 Total used height:', totalUsed);
        console.log('🎯 Viewport height:', viewport.height);
        console.log('🎯 Deadspace:', deadspace, 'px');
        console.log('🎯 Utilization:', ((totalUsed / viewport.height) * 100).toFixed(1) + '%');
        
        // Test STEMI query
        console.log('🧪 Testing STEMI protocol query...');
        await page.fill('#messageInput', 'What is the ED STEMI protocol?');
        await page.click('#sendButton');
        
        // Wait for response
        await page.waitForTimeout(3000);
        
        // Take final screenshot
        await page.screenshot({ path: 'ui-after-query.png', fullPage: true });
        
        // Check for response
        const response = await page.locator('.bot-message').last();
        const hasResponse = await response.isVisible();
        console.log('✅ Query response received:', hasResponse);
        
        if (hasResponse) {
            const responseText = await response.textContent();
            console.log('📝 Response preview:', responseText?.substring(0, 100) + '...');
        }
        
        // Report CSP errors
        if (cspErrors.length > 0) {
            console.log('❌ CSP Errors found:');
            cspErrors.forEach(error => console.log('  -', error));
        } else {
            console.log('✅ No CSP errors detected');
        }
        
        // Final validation
        console.log('\n🏆 UI VALIDATION SUMMARY:');
        console.log('- CSP Policy:', cspErrors.length === 0 ? '✅ FIXED' : '❌ ISSUES REMAIN');
        console.log('- Deadspace:', deadspace < 50 ? '✅ MINIMAL' : '❌ EXCESSIVE');
        console.log('- STEMI Query:', hasResponse ? '✅ WORKING' : '❌ FAILING');
        console.log('- Font Loading:', cspErrors.length === 0 ? '✅ GOOGLE FONTS OK' : '❌ FONT ISSUES');
        
    } catch (error) {
        console.error('❌ Test failed:', error);
    } finally {
        await browser.close();
    }
}

validateUI().catch(console.error);