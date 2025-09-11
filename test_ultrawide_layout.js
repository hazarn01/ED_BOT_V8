const { chromium } = require('playwright');

async function analyzeUltrawideLayout() {
    console.log('🖥️ Analyzing Ultrawide Monitor Layout...');
    
    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    
    try {
        // Test different ultrawide resolutions
        const ultrawideResolutions = [
            { width: 2560, height: 1080, name: '2560x1080 (21:9)' },
            { width: 3440, height: 1440, name: '3440x1440 (21:9)' },
            { width: 3840, height: 1600, name: '3840x1600 (24:10)' },
            { width: 5120, height: 1440, name: '5120x1440 (32:9)' }
        ];
        
        for (const resolution of ultrawideResolutions) {
            console.log(`\n📐 Testing ${resolution.name} resolution...`);
            
            await page.setViewportSize({ width: resolution.width, height: resolution.height });
            await page.goto('http://localhost:8001');
            await page.waitForLoadState('networkidle');
            await page.waitForTimeout(1000);
            
            // Get layout measurements
            const measurements = await page.evaluate(() => {
                const container = document.querySelector('.chat-container');
                const header = document.querySelector('.chat-header');
                const messages = document.querySelector('.chat-messages');
                const input = document.querySelector('.chat-input-container');
                
                const containerRect = container?.getBoundingClientRect();
                const headerRect = header?.getBoundingClientRect();
                const messagesRect = messages?.getBoundingClientRect();
                const inputRect = input?.getBoundingClientRect();
                
                return {
                    viewport: { width: window.innerWidth, height: window.innerHeight },
                    container: {
                        width: containerRect?.width || 0,
                        height: containerRect?.height || 0,
                        left: containerRect?.left || 0,
                        right: containerRect?.right || 0
                    },
                    header: { height: headerRect?.height || 0 },
                    messages: { height: messagesRect?.height || 0 },
                    input: { height: inputRect?.height || 0 },
                    deadSpaceLeft: containerRect?.left || 0,
                    deadSpaceRight: (window.innerWidth - (containerRect?.right || 0)),
                    utilization: containerRect ? (containerRect.width / window.innerWidth * 100) : 0
                };
            });
            
            console.log(`  Viewport: ${measurements.viewport.width}x${measurements.viewport.height}`);
            console.log(`  Container: ${measurements.container.width}x${measurements.container.height}`);
            console.log(`  Dead Space: Left ${measurements.deadSpaceLeft}px, Right ${measurements.deadSpaceRight}px`);
            console.log(`  Width Utilization: ${measurements.utilization.toFixed(1)}%`);
            
            // Identify issues
            const issues = [];
            if (measurements.utilization < 85) {
                issues.push(`Low width utilization (${measurements.utilization.toFixed(1)}%)`);
            }
            if (measurements.deadSpaceLeft > 100 || measurements.deadSpaceRight > 100) {
                issues.push('Excessive side deadspace');
            }
            if (measurements.container.width < resolution.width * 0.8) {
                issues.push('Container too narrow for ultrawide');
            }
            
            if (issues.length > 0) {
                console.log(`  ❌ Issues: ${issues.join(', ')}`);
            } else {
                console.log(`  ✅ Layout optimized for this resolution`);
            }
            
            // Take screenshot
            await page.screenshot({ 
                path: `ultrawide-${resolution.width}x${resolution.height}.png`, 
                fullPage: false 
            });
        }
        
        console.log('\n🎯 Ultrawide Analysis Complete');
        console.log('Screenshots saved for each resolution');
        
        // Test with sample query
        await page.setViewportSize({ width: 3440, height: 1440 });
        await page.goto('http://localhost:8001');
        await page.waitForLoadState('networkidle');
        
        console.log('\n🧪 Testing query on 3440x1440...');
        await page.fill('#messageInput', 'What is the ED STEMI protocol?');
        await page.click('#sendButton');
        await page.waitForTimeout(3000);
        
        const finalMeasurements = await page.evaluate(() => {
            const botMessage = document.querySelector('.bot-message .message-content');
            const messageRect = botMessage?.getBoundingClientRect();
            return {
                messageWidth: messageRect?.width || 0,
                viewportWidth: window.innerWidth,
                messageUtilization: messageRect ? (messageRect.width / window.innerWidth * 100) : 0
            };
        });
        
        console.log(`Message width: ${finalMeasurements.messageWidth}px`);
        console.log(`Message utilization: ${finalMeasurements.messageUtilization.toFixed(1)}%`);
        
        await page.screenshot({ path: 'ultrawide-with-message.png', fullPage: false });
        
    } catch (error) {
        console.error('❌ Analysis failed:', error.message);
        
        // Fallback: just report viewport size
        const viewport = await page.viewportSize();
        console.log(`Current viewport: ${viewport.width}x${viewport.height}`);
    } finally {
        await browser.close();
    }
}

analyzeUltrawideLayout().catch(console.error);