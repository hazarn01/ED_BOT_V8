#!/usr/bin/env python3
"""
Deploy Quality Monitoring - Setup continuous monitoring for ED Bot v8
PRP-48: Close the integration gap with automated monitoring deployment
"""

import os
import subprocess
import sys
from pathlib import Path
import json

class QualityMonitoringDeployer:
    """Deploy and configure continuous quality monitoring."""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.monitor_script = self.project_root / "scripts" / "continuous_quality_monitor.py"
        self.cron_command = None
    
    def check_prerequisites(self) -> bool:
        """Check if all prerequisites are met."""
        print("🔍 Checking prerequisites...")
        
        # Check if API is running
        try:
            import requests
            response = requests.get("http://localhost:8001/health", timeout=5)
            if response.status_code == 200:
                print("✅ API server is running")
            else:
                print("❌ API server not responding correctly")
                return False
        except Exception as e:
            print(f"❌ Cannot connect to API server: {e}")
            return False
        
        # Check if monitor script exists
        if not self.monitor_script.exists():
            print(f"❌ Monitor script not found: {self.monitor_script}")
            return False
        else:
            print("✅ Monitor script found")
        
        # Check Python dependencies
        try:
            import requests
            print("✅ Python requests library available")
        except ImportError:
            print("❌ Python requests library required")
            return False
        
        return True
    
    def test_single_monitoring_run(self) -> bool:
        """Test the monitoring script with a single run."""
        print("🧪 Testing monitoring script...")
        
        try:
            # Run single check
            result = subprocess.run([
                sys.executable, 
                str(self.monitor_script),
                "--threshold", "70"  # Lower threshold for testing
            ], capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                print("✅ Monitoring script test successful")
                print("📊 Test output:")
                print(result.stdout.split('\n')[-10:])  # Last 10 lines
                return True
            else:
                print("❌ Monitoring script test failed")
                print(result.stderr)
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ Monitoring script test timed out")
            return False
        except Exception as e:
            print(f"❌ Error testing monitoring script: {e}")
            return False
    
    def setup_systemd_service(self) -> bool:
        """Setup systemd service for continuous monitoring."""
        print("⚙️ Setting up systemd service...")
        
        service_content = f"""[Unit]
Description=ED Bot v8 Quality Monitor
After=network.target
Wants=network-online.target

[Service]
Type=simple
User={os.getenv('USER', 'root')}
WorkingDirectory={self.project_root}
Environment=PYTHONPATH={self.project_root}
ExecStart={sys.executable} {self.monitor_script} --continuous --interval 300 --threshold 80
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        
        service_file = "/tmp/edbot-quality-monitor.service"
        
        try:
            with open(service_file, "w") as f:
                f.write(service_content)
            
            print(f"✅ Service file created: {service_file}")
            print("📝 To install as system service:")
            print(f"   sudo cp {service_file} /etc/systemd/system/")
            print("   sudo systemctl daemon-reload")
            print("   sudo systemctl enable edbot-quality-monitor")
            print("   sudo systemctl start edbot-quality-monitor")
            
            return True
            
        except Exception as e:
            print(f"❌ Error creating service file: {e}")
            return False
    
    def setup_cron_job(self) -> bool:
        """Setup cron job as alternative to systemd."""
        print("⏰ Setting up cron job...")
        
        # Create wrapper script for cron
        wrapper_script = "/tmp/run_quality_monitor.sh"
        wrapper_content = f"""#!/bin/bash
cd {self.project_root}
export PYTHONPATH={self.project_root}
{sys.executable} {self.monitor_script} --continuous --interval 300 --threshold 80 >> /tmp/quality_monitor_cron.log 2>&1
"""
        
        try:
            with open(wrapper_script, "w") as f:
                f.write(wrapper_content)
            
            # Make executable
            os.chmod(wrapper_script, 0o755)
            
            print(f"✅ Cron wrapper script created: {wrapper_script}")
            print("📝 To install cron job, run:")
            print(f"   (crontab -l 2>/dev/null; echo '@reboot {wrapper_script}') | crontab -")
            print("   This will start monitoring on system boot")
            
            return True
            
        except Exception as e:
            print(f"❌ Error creating cron setup: {e}")
            return False
    
    def create_monitoring_dashboard_config(self) -> bool:
        """Create configuration for monitoring dashboard."""
        print("📊 Creating monitoring dashboard config...")
        
        dashboard_config = {
            "monitoring": {
                "api_url": "http://localhost:8001/api/v1/query",
                "check_interval": 300,  # 5 minutes
                "quality_threshold": 80,
                "failure_threshold": 3,
                "alert_cooldown": 300,
                "critical_queries": [
                    "what is the STEMI protocol",
                    "standard levophed dosing", 
                    "pediatric epinephrine dose",
                    "sepsis lactate criteria",
                    "RETU chest pain pathway",
                    "hypoglycemia treatment"
                ]
            },
            "alerting": {
                "log_file": "/tmp/quality_monitor.log",
                "alert_file": "/tmp/quality_alert.json",
                "data_file": "/tmp/quality_monitoring_data.json"
            },
            "deployment": {
                "service_name": "edbot-quality-monitor",
                "log_retention_days": 7,
                "data_retention_hours": 24
            }
        }
        
        config_file = self.project_root / "config" / "quality_monitoring.json"
        
        try:
            # Create config directory if it doesn't exist
            config_file.parent.mkdir(exist_ok=True)
            
            with open(config_file, "w") as f:
                json.dump(dashboard_config, f, indent=2)
            
            print(f"✅ Dashboard config created: {config_file}")
            return True
            
        except Exception as e:
            print(f"❌ Error creating dashboard config: {e}")
            return False
    
    def deploy_full_monitoring_suite(self):
        """Deploy complete monitoring solution."""
        print("🚀 DEPLOYING ED BOT V8 QUALITY MONITORING SUITE")
        print("="*60)
        
        steps = [
            ("Prerequisites Check", self.check_prerequisites),
            ("Single Run Test", self.test_single_monitoring_run),
            ("Systemd Service Setup", self.setup_systemd_service),
            ("Cron Job Setup", self.setup_cron_job), 
            ("Dashboard Config", self.create_monitoring_dashboard_config)
        ]
        
        success_count = 0
        for step_name, step_func in steps:
            print(f"\n📋 Step: {step_name}")
            try:
                if step_func():
                    success_count += 1
                    print(f"✅ {step_name} - SUCCESS")
                else:
                    print(f"❌ {step_name} - FAILED")
            except Exception as e:
                print(f"❌ {step_name} - ERROR: {e}")
        
        print("\n" + "="*60)
        print(f"📊 DEPLOYMENT SUMMARY: {success_count}/{len(steps)} steps successful")
        
        if success_count == len(steps):
            print("🎉 DEPLOYMENT COMPLETE!")
            print("\n🚀 NEXT STEPS:")
            print("1. Choose deployment method:")
            print("   • For systemd: Follow the systemd service instructions above")  
            print("   • For cron: Follow the cron job instructions above")
            print("\n2. Monitor the monitoring:")
            print("   • Logs: tail -f /tmp/quality_monitor.log")
            print("   • Alerts: watch cat /tmp/quality_alert.json")
            print("   • Data: cat /tmp/quality_monitoring_data.json")
            print("\n3. Test manual trigger:")
            print(f"   • {sys.executable} {self.monitor_script}")
            
        else:
            print("⚠️ DEPLOYMENT INCOMPLETE - Some steps failed")
            print("Please resolve the issues above and try again")
        
        return success_count == len(steps)

def main():
    """Deploy quality monitoring with command line options."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Deploy ED Bot v8 Quality Monitoring")
    parser.add_argument("--test-only", action="store_true", help="Only run prerequisites and test")
    
    args = parser.parse_args()
    
    deployer = QualityMonitoringDeployer()
    
    if args.test_only:
        print("🧪 TESTING MONITORING SETUP")
        print("="*40)
        if deployer.check_prerequisites():
            deployer.test_single_monitoring_run()
    else:
        deployer.deploy_full_monitoring_suite()

if __name__ == "__main__":
    main()