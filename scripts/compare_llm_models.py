#!/usr/bin/env python3
"""
Compare LLM model outputs for medical queries.

This script compares responses from different LLM backends (GPT-OSS vs Ollama)
to evaluate quality, completeness, and accuracy of medical responses.
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from typing import Any, Dict, List

from tabulate import tabulate

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ai.gpt_oss_client import GPTOSSClient
from src.ai.llm_client import UnifiedLLMClient
from src.ai.ollama_client import OllamaClient
from src.utils.logging import get_logger

logger = get_logger(__name__)


class ModelComparer:
    """Compare outputs from different LLM models."""
    
    def __init__(self):
        self.test_queries = [
            {
                "query": "What is the complete STEMI protocol including timing requirements?",
                "category": "PROTOCOL",
                "key_elements": ["door-to-balloon", "90 minutes", "EKG", "aspirin", "PCI"]
            },
            {
                "query": "Calculate pediatric epinephrine dose for 25kg child with anaphylaxis",
                "category": "DOSAGE",
                "key_elements": ["0.01 mg/kg", "0.25mg", "1:1000", "intramuscular", "thigh"]
            },
            {
                "query": "List ICU admission criteria for severe pneumonia",
                "category": "CRITERIA",
                "key_elements": ["respiratory rate", "oxygen", "confusion", "blood pressure", "multilobar"]
            },
            {
                "query": "Differential diagnosis for chest pain with elevated troponin and normal EKG",
                "category": "DIAGNOSTIC",
                "key_elements": ["myocarditis", "pulmonary embolism", "takotsubo", "demand ischemia"]
            },
            {
                "query": "Summarize the sepsis bundle requirements within first hour",
                "category": "SUMMARY",
                "key_elements": ["lactate", "blood cultures", "antibiotics", "fluids", "vasopressors"]
            }
        ]
        
        self.results = []
        
    async def test_gpt_oss(self, query: str) -> Dict[str, Any]:
        """Test GPT-OSS 20B model."""
        try:
            client = GPTOSSClient(
                base_url="http://localhost:8002",
                model="TheBloke/GPT-OSS-20B-GPTQ"
            )
            
            start_time = time.time()
            response = await client.generate(
                prompt=f"As a medical professional, please answer: {query}",
                temperature=0.0,
                max_tokens=1500
            )
            elapsed = time.time() - start_time
            
            return {
                "model": "GPT-OSS 20B",
                "response": response,
                "time": elapsed,
                "tokens": len(response.split()),
                "success": True
            }
        except Exception as e:
            logger.error(f"GPT-OSS error: {e}")
            return {
                "model": "GPT-OSS 20B",
                "response": f"Error: {str(e)}",
                "time": 0,
                "tokens": 0,
                "success": False
            }
            
    async def test_ollama(self, query: str) -> Dict[str, Any]:
        """Test Ollama/Mistral model."""
        try:
            client = OllamaClient(
                base_url="http://localhost:11434",
                model="mistral:7b-instruct"
            )
            
            start_time = time.time()
            response = await client.generate(
                prompt=f"As a medical professional, please answer: {query}",
                temperature=0.0,
                max_tokens=1500
            )
            elapsed = time.time() - start_time
            
            return {
                "model": "Mistral 7B",
                "response": response,
                "time": elapsed,
                "tokens": len(response.split()),
                "success": True
            }
        except Exception as e:
            logger.error(f"Ollama error: {e}")
            return {
                "model": "Mistral 7B", 
                "response": f"Error: {str(e)}",
                "time": 0,
                "tokens": 0,
                "success": False
            }
            
    async def test_unified(self, query: str) -> Dict[str, Any]:
        """Test Unified client with fallback."""
        try:
            client = UnifiedLLMClient(
                primary_backend="gpt-oss",
                enable_fallback=True
            )
            
            start_time = time.time()
            response = await client.generate(
                prompt=f"As a medical professional, please answer: {query}",
                temperature=0.0,
                max_tokens=1500
            )
            elapsed = time.time() - start_time
            
            active_backend = client.get_active_backend()
            
            return {
                "model": f"Unified ({active_backend})",
                "response": response,
                "time": elapsed,
                "tokens": len(response.split()),
                "success": True,
                "backend": active_backend
            }
        except Exception as e:
            logger.error(f"Unified client error: {e}")
            return {
                "model": "Unified",
                "response": f"Error: {str(e)}",
                "time": 0,
                "tokens": 0,
                "success": False
            }
            
    def evaluate_response(self, response: str, key_elements: List[str]) -> Dict[str, Any]:
        """Evaluate response quality based on key elements."""
        response_lower = response.lower()
        
        # Count how many key elements are present
        elements_found = []
        elements_missing = []
        
        for element in key_elements:
            if element.lower() in response_lower:
                elements_found.append(element)
            else:
                elements_missing.append(element)
                
        completeness = len(elements_found) / len(key_elements) if key_elements else 0
        
        # Check for medical safety indicators
        has_citation = "source:" in response_lower or "reference:" in response_lower
        has_warning = "consult" in response_lower or "seek medical" in response_lower
        is_detailed = len(response) > 200
        
        return {
            "completeness": completeness,
            "elements_found": elements_found,
            "elements_missing": elements_missing,
            "has_citation": has_citation,
            "has_warning": has_warning,
            "is_detailed": is_detailed,
            "quality_score": completeness * 0.5 + (0.2 if has_citation else 0) + (0.2 if is_detailed else 0) + (0.1 if has_warning else 0)
        }
        
    async def compare_models(self):
        """Run comparison across all test queries."""
        print("\n" + "="*80)
        print("🔬 LLM Model Comparison - Medical Query Responses")
        print("="*80 + "\n")
        
        for test_case in self.test_queries:
            query = test_case["query"]
            category = test_case["category"]
            key_elements = test_case["key_elements"]
            
            print(f"\n📋 Query ({category}): {query[:80]}...")
            print("-" * 80)
            
            # Test all models
            tasks = [
                self.test_gpt_oss(query),
                self.test_ollama(query),
                self.test_unified(query)
            ]
            
            results = await asyncio.gather(*tasks)
            
            # Evaluate each response
            comparison_data = []
            for result in results:
                if result["success"]:
                    eval_result = self.evaluate_response(result["response"], key_elements)
                    comparison_data.append({
                        "Model": result["model"],
                        "Time (s)": f"{result['time']:.2f}",
                        "Tokens": result["tokens"],
                        "Completeness": f"{eval_result['completeness']*100:.0f}%",
                        "Quality": f"{eval_result['quality_score']:.2f}",
                        "Citation": "✓" if eval_result["has_citation"] else "✗",
                        "Detailed": "✓" if eval_result["is_detailed"] else "✗"
                    })
                    
                    # Store full results
                    self.results.append({
                        "query": query,
                        "category": category,
                        "model": result["model"],
                        "response": result["response"],
                        "metrics": eval_result,
                        "performance": {
                            "time": result["time"],
                            "tokens": result["tokens"]
                        }
                    })
                else:
                    comparison_data.append({
                        "Model": result["model"],
                        "Time (s)": "N/A",
                        "Tokens": 0,
                        "Completeness": "N/A",
                        "Quality": "0.00",
                        "Citation": "✗",
                        "Detailed": "✗"
                    })
            
            # Display comparison table
            print(tabulate(comparison_data, headers="keys", tablefmt="grid"))
            
            # Show missing elements for best response
            best_result = max(
                [r for r in results if r["success"]], 
                key=lambda x: len(x["response"]),
                default=None
            )
            
            if best_result:
                eval_result = self.evaluate_response(best_result["response"], key_elements)
                if eval_result["elements_missing"]:
                    print(f"\n⚠️  Missing elements in best response ({best_result['model']}):")
                    for element in eval_result["elements_missing"]:
                        print(f"   - {element}")
                        
        # Summary statistics
        self._print_summary()
        
        # Save detailed results
        self._save_results()
        
    def _print_summary(self):
        """Print summary statistics."""
        print("\n" + "="*80)
        print("📊 SUMMARY STATISTICS")
        print("="*80)
        
        if not self.results:
            print("No results to summarize")
            return
            
        # Group by model
        model_stats = {}
        for result in self.results:
            model = result["model"]
            if model not in model_stats:
                model_stats[model] = {
                    "queries": 0,
                    "total_time": 0,
                    "total_tokens": 0,
                    "total_quality": 0,
                    "total_completeness": 0
                }
            
            stats = model_stats[model]
            stats["queries"] += 1
            stats["total_time"] += result["performance"]["time"]
            stats["total_tokens"] += result["performance"]["tokens"]
            stats["total_quality"] += result["metrics"]["quality_score"]
            stats["total_completeness"] += result["metrics"]["completeness"]
            
        # Calculate averages
        summary_data = []
        for model, stats in model_stats.items():
            n = stats["queries"]
            if n > 0:
                summary_data.append({
                    "Model": model,
                    "Avg Time (s)": f"{stats['total_time']/n:.2f}",
                    "Avg Tokens": f"{stats['total_tokens']/n:.0f}",
                    "Avg Quality": f"{stats['total_quality']/n:.2f}",
                    "Avg Completeness": f"{stats['total_completeness']/n*100:.0f}%"
                })
        
        print(tabulate(summary_data, headers="keys", tablefmt="grid"))
        
        # Determine winner
        if summary_data:
            best_quality = max(summary_data, key=lambda x: float(x["Avg Quality"].strip()))
            fastest = min(summary_data, key=lambda x: float(x["Avg Time (s)"].strip()))
            
            print(f"\n🏆 Best Quality: {best_quality['Model']} (Score: {best_quality['Avg Quality']})")
            print(f"⚡ Fastest: {fastest['Model']} ({fastest['Avg Time (s)']}s avg)")
            
    def _save_results(self):
        """Save detailed results to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"model_comparison_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)
            
        print(f"\n💾 Detailed results saved to: {filename}")


async def main():
    """Main entry point."""
    comparer = ModelComparer()
    
    try:
        await comparer.compare_models()
    except KeyboardInterrupt:
        print("\n\n⚠️  Comparison interrupted by user")
    except Exception as e:
        print(f"\n❌ Error during comparison: {e}")
        logger.error(f"Comparison failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())