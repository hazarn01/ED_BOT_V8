const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

async function testResponsiveUI() {
  console.log('🚀 Starting Playwright UI Testing for Dead Space Detection');
  
  const browser = await chromium.launch();
  const context = await browser.newContext();
  const page = await context.newPage();
  
  // Create screenshots directory
  const screenshotsDir = './ui-screenshots';
  if (!fs.existsSync(screenshotsDir)) {
    fs.mkdirSync(screenshotsDir);
  }
  
  // Test breakpoints from PRP-40
  const breakpoints = [
    { name: 'mobile-sm', width: 320, height: 568 },
    { name: 'mobile-md', width: 375, height: 667 },
    { name: 'mobile-lg', width: 414, height: 896 },
    { name: 'tablet', width: 768, height: 1024 },
    { name: 'laptop', width: 1024, height: 768 },
    { name: 'desktop', width: 1200, height: 800 },
    { name: 'desktop-lg', width: 1440, height: 900 },
    { name: 'desktop-xl', width: 1920, height: 1080 },
    { name: 'ultrawide', width: 2560, height: 1440 },
    { name: 'ultrawide-xl', width: 3440, height: 1440 }
  ];
  
  try {
    console.log('📱 Navigating to ED Bot UI...');
    await page.goto('http://localhost:8001');
    await page.waitForLoadState('networkidle');
    
    // Wait for content to load
    await page.waitForSelector('.chat-container');
    
    console.log('🔍 Testing responsiveness across breakpoints...');
    
    for (const breakpoint of breakpoints) {
      console.log(`📏 Testing ${breakpoint.name} (${breakpoint.width}x${breakpoint.height})`);
      
      // Set viewport size
      await page.setViewportSize({ 
        width: breakpoint.width, 
        height: breakpoint.height 
      });
      
      // Wait for layout to settle
      await page.waitForTimeout(500);
      
      // Take screenshot
      const filename = `${breakpoint.name}_${breakpoint.width}x${breakpoint.height}.png`;
      await page.screenshot({ 
        path: path.join(screenshotsDir, filename),
        fullPage: true
      });
      
      // Get container dimensions and detect dead space
      const containerInfo = await page.evaluate(() => {
        const container = document.querySelector('.chat-container');
        const body = document.body;
        const viewport = {
          width: window.innerWidth,
          height: window.innerHeight
        };
        
        if (container) {
          const containerRect = container.getBoundingClientRect();
          const computedStyle = window.getComputedStyle(container);
          
          return {
            viewport,
            container: {
              width: containerRect.width,
              left: containerRect.left,
              right: containerRect.right,
              marginLeft: computedStyle.marginLeft,
              marginRight: computedStyle.marginRight,
              maxWidth: computedStyle.maxWidth,
              padding: computedStyle.padding
            },
            deadSpace: {
              left: containerRect.left,
              right: viewport.width - containerRect.right,
              total: (containerRect.left) + (viewport.width - containerRect.right)
            }
          };
        }
        return null;
      });
      
      // Log dead space analysis
      if (containerInfo) {
        const deadSpacePercent = (containerInfo.deadSpace.total / containerInfo.viewport.width) * 100;
        console.log(`  📊 Container: ${containerInfo.container.width}px wide`);
        console.log(`  📊 Dead space: ${containerInfo.deadSpace.total}px (${deadSpacePercent.toFixed(1)}%)`);
        console.log(`  📊 Left margin: ${containerInfo.deadSpace.left}px`);
        console.log(`  📊 Right margin: ${containerInfo.deadSpace.right}px`);
        console.log(`  📊 CSS max-width: ${containerInfo.container.maxWidth}`);
        
        if (deadSpacePercent > 5) {
          console.log(`  ⚠️  DEAD SPACE DETECTED: ${deadSpacePercent.toFixed(1)}% unused space!`);
        }
      }
      
      console.log(''); // Add spacing
    }
    
    console.log('✅ Screenshot capture complete!');
    console.log(`📁 Screenshots saved to: ${path.resolve(screenshotsDir)}`);
    
  } catch (error) {
    console.error('❌ Error during testing:', error);
  } finally {
    await browser.close();
  }
}

// Run the test
testResponsiveUI().catch(console.error);