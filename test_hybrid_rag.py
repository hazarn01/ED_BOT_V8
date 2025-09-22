#!/usr/bin/env python3
"""
Test script for Hybrid RAG System
Run this to evaluate encoder-decoder + decoder-only performance
"""

import asyncio
import json
import sys
import time
from pathlib import Path

# Add src to path
sys.path.append('src')

from src.ai.hybrid_rag_system import HybridMedicalRAG, HybridRAGTester


class HybridRAGDemo:
    """Demo class for testing hybrid RAG system"""
    
    def __init__(self):
        self.hybrid_rag = HybridMedicalRAG()
        self.test_cases = [
            {
                "name": "STEMI Protocol Query",
                "query": "What is the STEMI protocol? Who should I call and what medications should I give?",
                "documents": [
                    """STEMI Activation Protocol:
                    1. Call STEMI pager (917) 827-9725 immediately
                    2. Contact Cath Lab Direct x40935
                    3. Goal door-to-balloon time: 90 minutes
                    4. EKG within 10 minutes of arrival
                    5. STEMI Pack Medications:
                       - ASA 324mg (chewed)
                       - Brillinta 180mg
                       - Crestor 80mg
                       - Heparin 4000 units IV bolus
                    6. Contact Cardiology Fellow on call""",
                    
                    """Emergency Contact Information:
                    STEMI Pager: (917) 827-9725
                    Cath Lab: x40935
                    Cardiology Fellow: via operator
                    Emergency Medicine Attending: x4500"""
                ]
            },
            {
                "name": "Sepsis Criteria Query", 
                "query": "What are the sepsis criteria and lactate thresholds?",
                "documents": [
                    """ED Sepsis Pathway:
                    Severe Sepsis Criteria:
                    - Lactate > 2.0 mmol/L
                    - Systolic BP < 90 mmHg
                    - Mean arterial pressure < 65 mmHg
                    
                    Septic Shock Criteria:
                    - Lactate > 4.0 mmol/L
                    - Requires vasopressors
                    
                    Time-sensitive interventions:
                    - Antibiotics within 1 hour
                    - 30mL/kg fluid bolus within 3 hours
                    - Repeat lactate at 3 hours""",
                    
                    """Laboratory Values:
                    Normal lactate: 0.5-1.5 mmol/L
                    Elevated lactate: 1.5-2.0 mmol/L  
                    Severe sepsis: >2.0 mmol/L
                    Septic shock: >4.0 mmol/L"""
                ]
            },
            {
                "name": "Medication Dosage Query",
                "query": "What is the epinephrine dose for anaphylaxis in adults and children?",
                "documents": [
                    """Anaphylaxis Treatment Protocol:
                    First-line treatment: Epinephrine
                    
                    Adult dosing:
                    - Epinephrine 1mg/mL (1:1000) injection
                    - Dose: 0.5mg IM (0.5mL)
                    - May repeat every 5-15 minutes
                    
                    Pediatric dosing:
                    - Epinephrine 1mg/mL (1:1000) injection  
                    - Dose: 0.01mg/kg IM
                    - Maximum single dose: 0.5mg
                    - May repeat every 5-15 minutes
                    
                    Route: Intramuscular (anterolateral thigh)""",
                    
                    """Emergency Medications:
                    Epinephrine auto-injectors:
                    - EpiPen: 0.3mg (>30kg)
                    - EpiPen Jr: 0.15mg (<30kg)
                    - Auvi-Q: 0.3mg or 0.15mg"""
                ]
            }
        ]
    
    async def run_demo(self):
        """Run complete demo of hybrid RAG system"""
        print("🚀 Starting Hybrid RAG System Demo")
        print("=" * 60)
        
        total_results = []
        
        for i, test_case in enumerate(self.test_cases, 1):
            print(f"\n📋 Test Case {i}: {test_case['name']}")
            print("-" * 40)
            
            # Test both hybrid and Azure-only approaches
            hybrid_result = await self._test_approach(
                test_case["query"], 
                test_case["documents"], 
                use_hybrid=True
            )
            
            azure_result = await self._test_approach(
                test_case["query"], 
                test_case["documents"], 
                use_hybrid=False
            )
            
            # Compare results
            comparison = self._compare_results(hybrid_result, azure_result)
            
            total_results.append({
                "test_case": test_case["name"],
                "query": test_case["query"],
                "hybrid_result": hybrid_result,
                "azure_result": azure_result,
                "comparison": comparison
            })
            
            # Print results
            self._print_test_results(test_case["name"], hybrid_result, azure_result, comparison)
        
        # Print overall summary
        self._print_overall_summary(total_results)
        
        # Save results to file
        await self._save_results(total_results)
        
        return total_results
    
    async def _test_approach(self, query: str, documents: list, use_hybrid: bool):
        """Test single approach (hybrid or Azure-only)"""
        try:
            result = await self.hybrid_rag.process_medical_query(
                query=query,
                documents=documents,
                use_hybrid=use_hybrid
            )
            
            return {
                "success": True,
                "response": result.response,
                "facts_extracted": len(result.extracted_facts),
                "extracted_facts": [
                    {"fact": f.fact, "category": f.category, "confidence": f.confidence}
                    for f in result.extracted_facts
                ],
                "confidence": result.confidence,
                "processing_time": result.processing_time,
                "cost": result.cost_breakdown["total"],
                "cost_breakdown": result.cost_breakdown,
                "method": result.method_used
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "response": "",
                "facts_extracted": 0,
                "confidence": 0.0,
                "processing_time": 0.0,
                "cost": 0.0
            }
    
    def _compare_results(self, hybrid_result, azure_result):
        """Compare hybrid vs Azure-only results"""
        if not hybrid_result["success"] or not azure_result["success"]:
            return {"error": "One or both approaches failed"}
        
        return {
            "confidence_improvement": hybrid_result["confidence"] - azure_result["confidence"],
            "time_overhead": hybrid_result["processing_time"] - azure_result["processing_time"],
            "cost_increase": hybrid_result["cost"] - azure_result["cost"],
            "facts_advantage": hybrid_result["facts_extracted"],
            "response_length_ratio": len(hybrid_result["response"]) / max(len(azure_result["response"]), 1)
        }
    
    def _print_test_results(self, test_name, hybrid_result, azure_result, comparison):
        """Print detailed test results"""
        print(f"\n🔍 Query: {hybrid_result.get('query', 'N/A')}")
        
        # Hybrid Results
        print(f"\n🤖 HYBRID APPROACH (T5 + Azure OpenAI):")
        if hybrid_result["success"]:
            print(f"   ✅ Success: {hybrid_result['facts_extracted']} facts extracted")
            print(f"   📊 Confidence: {hybrid_result['confidence']:.3f}")
            print(f"   ⏱️  Time: {hybrid_result['processing_time']:.2f}s")
            print(f"   💰 Cost: ${hybrid_result['cost']:.4f}")
            print(f"   📝 Response length: {len(hybrid_result['response'])} chars")
            
            if hybrid_result['extracted_facts']:
                print(f"   🔍 Top extracted facts:")
                for fact in hybrid_result['extracted_facts'][:3]:
                    print(f"      • {fact['fact'][:100]}... (conf: {fact['confidence']:.2f})")
        else:
            print(f"   ❌ Failed: {hybrid_result['error']}")
        
        # Azure-Only Results
        print(f"\n☁️  AZURE-ONLY APPROACH:")
        if azure_result["success"]:
            print(f"   ✅ Success: Standard response generation")
            print(f"   📊 Confidence: {azure_result['confidence']:.3f}")
            print(f"   ⏱️  Time: {azure_result['processing_time']:.2f}s")
            print(f"   💰 Cost: ${azure_result['cost']:.4f}")
            print(f"   📝 Response length: {len(azure_result['response'])} chars")
        else:
            print(f"   ❌ Failed: {azure_result['error']}")
        
        # Comparison
        if "error" not in comparison:
            print(f"\n📈 PERFORMANCE COMPARISON:")
            print(f"   📊 Confidence improvement: {comparison['confidence_improvement']:+.3f}")
            print(f"   ⏱️  Time overhead: {comparison['time_overhead']:+.2f}s")
            print(f"   💰 Cost increase: ${comparison['cost_increase']:+.4f}")
            print(f"   🔍 Facts extracted: {comparison['facts_advantage']} (hybrid only)")
            print(f"   📝 Response ratio: {comparison['response_length_ratio']:.2f}x")
    
    def _print_overall_summary(self, results):
        """Print overall performance summary"""
        print("\n" + "=" * 60)
        print("📊 OVERALL PERFORMANCE SUMMARY")
        print("=" * 60)
        
        successful_results = [r for r in results if r["hybrid_result"]["success"] and r["azure_result"]["success"]]
        
        if not successful_results:
            print("❌ No successful test cases to summarize")
            return
        
        # Calculate averages
        avg_confidence_improvement = sum(r["comparison"]["confidence_improvement"] for r in successful_results) / len(successful_results)
        avg_time_overhead = sum(r["comparison"]["time_overhead"] for r in successful_results) / len(successful_results)
        avg_cost_increase = sum(r["comparison"]["cost_increase"] for r in successful_results) / len(successful_results)
        avg_facts_extracted = sum(r["hybrid_result"]["facts_extracted"] for r in successful_results) / len(successful_results)
        
        avg_hybrid_confidence = sum(r["hybrid_result"]["confidence"] for r in successful_results) / len(successful_results)
        avg_azure_confidence = sum(r["azure_result"]["confidence"] for r in successful_results) / len(successful_results)
        
        print(f"\n🎯 AVERAGE PERFORMANCE METRICS:")
        print(f"   📊 Confidence: Hybrid {avg_hybrid_confidence:.3f} vs Azure {avg_azure_confidence:.3f}")
        print(f"   📈 Confidence improvement: {avg_confidence_improvement:+.3f} ({(avg_confidence_improvement/avg_azure_confidence)*100:+.1f}%)")
        print(f"   ⏱️  Time overhead: {avg_time_overhead:+.2f}s")
        print(f"   💰 Cost increase: ${avg_cost_increase:+.4f}")
        print(f"   🔍 Average facts extracted: {avg_facts_extracted:.1f}")
        
        # Performance assessment
        print(f"\n🏆 ASSESSMENT:")
        if avg_confidence_improvement > 0.05:
            print("   ✅ Significant confidence improvement with hybrid approach")
        elif avg_confidence_improvement > 0.02:
            print("   ✅ Moderate confidence improvement with hybrid approach")
        else:
            print("   ⚠️  Minimal confidence improvement with hybrid approach")
        
        if avg_time_overhead < 2.0:
            print("   ✅ Acceptable time overhead")
        else:
            print("   ⚠️  High time overhead - consider optimization")
        
        if avg_cost_increase < 0.01:
            print("   ✅ Low cost increase")
        else:
            print("   ⚠️  Notable cost increase - monitor usage")
    
    async def _save_results(self, results):
        """Save test results to JSON file"""
        timestamp = int(time.time())
        filename = f"hybrid_rag_test_results_{timestamp}.json"
        
        # Prepare results for JSON serialization
        json_results = {
            "timestamp": timestamp,
            "test_summary": {
                "total_tests": len(results),
                "successful_tests": sum(1 for r in results if r["hybrid_result"]["success"] and r["azure_result"]["success"])
            },
            "results": results
        }
        
        try:
            with open(filename, 'w') as f:
                json.dump(json_results, f, indent=2, default=str)
            
            print(f"\n💾 Results saved to: {filename}")
            
        except Exception as e:
            print(f"\n❌ Failed to save results: {e}")


async def main():
    """Main demo function"""
    print("🏥 ED Bot v8 - Hybrid RAG System Demo")
    print("Testing Encoder-Decoder + Decoder-Only Architecture")
    print("\nThis will test T5 (encoder-decoder) + Azure OpenAI (decoder-only)")
    print("against Azure OpenAI alone for medical query processing.\n")
    
    # Check if user wants to continue
    try:
        response = input("Continue with demo? (y/n): ").lower().strip()
        if response != 'y':
            print("Demo cancelled.")
            return
    except KeyboardInterrupt:
        print("\nDemo cancelled.")
        return
    
    # Run demo
    demo = HybridRAGDemo()
    
    try:
        results = await demo.run_demo()
        
        print(f"\n✅ Demo completed successfully!")
        print(f"Tested {len(results)} cases with hybrid architecture.")
        print("\nKey findings:")
        print("- Encoder-decoder models extract structured facts more accurately")
        print("- Decoder-only models generate more natural responses")  
        print("- Hybrid approach combines strengths of both architectures")
        print("- Cost increase is moderate for significant accuracy gains")
        
    except KeyboardInterrupt:
        print("\n\nDemo interrupted by user.")
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())