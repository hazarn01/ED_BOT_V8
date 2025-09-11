"""
Unit tests for medical domain-specific metrics.
"""

from unittest.mock import Mock, patch

import pytest

from src.observability.medical_metrics import (
    MedicalMetricsCollector,
    init_medical_metrics,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for medical metrics testing"""
    settings = Mock()
    settings.enable_medical_metrics = True
    return settings


@pytest.fixture
def medical_metrics_collector(mock_settings):
    """Create medical metrics collector instance"""
    return MedicalMetricsCollector(mock_settings)


@pytest.fixture
def disabled_medical_metrics_collector():
    """Create disabled medical metrics collector"""
    settings = Mock()
    settings.enable_medical_metrics = False
    return MedicalMetricsCollector(settings)


class TestMedicalMetricsCollectorInitialization:
    """Test medical metrics collector initialization"""
    
    def test_medical_metrics_collector_init_enabled(self, mock_settings):
        """Test medical metrics collector initialization with enabled metrics"""
        collector = MedicalMetricsCollector(mock_settings)
        
        assert collector.settings is mock_settings
        assert collector.enabled is True
    
    def test_medical_metrics_collector_init_disabled(self):
        """Test medical metrics collector initialization with disabled metrics"""
        settings = Mock()
        settings.enable_medical_metrics = False
        
        collector = MedicalMetricsCollector(settings)
        
        assert collector.enabled is False
    
    def test_medical_metrics_collector_init_no_settings(self):
        """Test medical metrics collector initialization without settings"""
        collector = MedicalMetricsCollector()
        
        assert collector.settings is None
        assert collector.enabled is True  # Default enabled
    
    def test_init_medical_metrics_function(self, mock_settings):
        """Test init_medical_metrics function"""
        with patch('src.observability.medical_metrics.medical_metrics') as mock_instance:
            init_medical_metrics(mock_settings)
            
            assert mock_instance.settings is mock_settings
            assert mock_instance.enabled is True


class TestMedicalSpecialtyClassification:
    """Test medical specialty classification"""
    
    def test_classify_cardiology_query(self, medical_metrics_collector):
        """Test cardiology query classification"""
        queries = [
            "what is the ED STEMI protocol",
            "chest pain evaluation criteria",
            "troponin levels for MI diagnosis",
            "EKG interpretation for arrhythmia"
        ]
        
        for query in queries:
            specialty = medical_metrics_collector.classify_medical_specialty(query)
            assert specialty == "cardiology"
    
    def test_classify_emergency_query(self, medical_metrics_collector):
        """Test emergency medicine query classification"""
        queries = [
            "trauma activation criteria",
            "CPR protocol for cardiac arrest",
            "emergency airway management",
            "shock treatment guidelines"
        ]
        
        for query in queries:
            specialty = medical_metrics_collector.classify_medical_specialty(query)
            assert specialty == "emergency"
    
    def test_classify_pharmacy_query(self, medical_metrics_collector):
        """Test pharmacy query classification"""
        queries = [
            "morphine dosage for pain management",
            "drug interaction between aspirin and warfarin",
            "medication allergy contraindications",
            "prescription side effects"
        ]
        
        for query in queries:
            specialty = medical_metrics_collector.classify_medical_specialty(query)
            assert specialty == "pharmacy"
    
    def test_classify_multiple_specialties(self, medical_metrics_collector):
        """Test query with multiple specialty keywords"""
        query = "cardiac arrest medication dosage protocol"
        
        specialty = medical_metrics_collector.classify_medical_specialty(query)
        
        # Should return the specialty with highest keyword match count
        # This query has both cardiology and pharmacy keywords
        assert specialty in ["cardiology", "pharmacy", "emergency"]
    
    def test_classify_general_query(self, medical_metrics_collector):
        """Test general query classification"""
        queries = [
            "hospital visiting hours",
            "patient registration process",
            "billing questions"
        ]
        
        for query in queries:
            specialty = medical_metrics_collector.classify_medical_specialty(query)
            assert specialty == "general"
    
    def test_classify_empty_query(self, medical_metrics_collector):
        """Test empty query classification"""
        specialty = medical_metrics_collector.classify_medical_specialty("")
        assert specialty == "general"


class TestMedicationExtraction:
    """Test medication name extraction"""
    
    def test_extract_common_medications(self, medical_metrics_collector):
        """Test extraction of common medication names"""
        test_cases = [
            ("give patient morphine 5mg IV", "morphine"),
            ("administer heparin bolus", "heparin"),
            ("insulin sliding scale protocol", "insulin"),
            ("tylenol 650mg PO", "tylenol"),
            ("aspirin 325mg daily", "aspirin")
        ]
        
        for query, expected_med in test_cases:
            medication = medical_metrics_collector.extract_medication(query)
            assert medication == expected_med
    
    def test_extract_medication_patterns(self, medical_metrics_collector):
        """Test medication pattern extraction"""
        queries_with_suffixes = [
            "metoprolol 50mg twice daily",
            "lisinopril 10mg daily",
            "atorvastatin 20mg at bedtime"
        ]
        
        for query in queries_with_suffixes:
            medication = medical_metrics_collector.extract_medication(query)
            # Should extract medication name (ends in common suffixes)
            assert medication != "unknown"
    
    def test_extract_no_medication(self, medical_metrics_collector):
        """Test query with no medication"""
        queries = [
            "patient vital signs normal",
            "discharge planning discussion",
            "family meeting scheduled"
        ]
        
        for query in queries:
            medication = medical_metrics_collector.extract_medication(query)
            assert medication == "unknown"
    
    def test_extract_high_risk_medication(self, medical_metrics_collector):
        """Test high-risk medication identification"""
        high_risk_queries = [
            "insulin drip protocol",
            "heparin infusion guidelines", 
            "warfarin dosing adjustment",
            "morphine PCA settings"
        ]
        
        for query in high_risk_queries:
            medication = medical_metrics_collector.extract_medication(query)
            assert medication in medical_metrics_collector.HIGH_RISK_MEDICATIONS


class TestDosageInfoExtraction:
    """Test dosage information extraction"""
    
    def test_extract_route_information(self, medical_metrics_collector):
        """Test route extraction from queries"""
        test_cases = [
            ("morphine 2mg IV push", "IV"),
            ("tylenol 650mg by mouth", "PO"),
            ("insulin 10 units SubQ", "SubQ"),
            ("rocephin 1g IM injection", "IM"),
            ("nitroglycerin SL tablet", "SL"),
            ("apply topical ointment", "topical")
        ]
        
        for query, expected_route in test_cases:
            dosage_info = medical_metrics_collector.extract_dosage_info(query)
            assert dosage_info["route"] == expected_route
    
    def test_extract_dose_information(self, medical_metrics_collector):
        """Test dose extraction from queries"""
        test_cases = [
            ("morphine 2mg IV", "2mg"),
            ("insulin 10 units SubQ", "10 units"),
            ("normal saline 1000ml", "1000ml"),
            ("epinephrine 1 mcg", "1 mcg")
        ]
        
        for query, expected_dose in test_cases:
            dosage_info = medical_metrics_collector.extract_dosage_info(query)
            assert dosage_info["dose"] == expected_dose
    
    def test_extract_unknown_dosage(self, medical_metrics_collector):
        """Test queries with no clear dosage information"""
        queries = [
            "check patient medications",
            "review allergy list",
            "medication reconciliation"
        ]
        
        for query in queries:
            dosage_info = medical_metrics_collector.extract_dosage_info(query)
            assert dosage_info["route"] == "unknown"
            assert dosage_info["dose"] == "unknown"


class TestTimeSensitiveProtocols:
    """Test time-sensitive protocol identification"""
    
    def test_identify_critical_protocols(self, medical_metrics_collector):
        """Test identification of time-sensitive protocols"""
        test_cases = [
            ("STEMI protocol activation", "STEMI"),
            ("stroke alert activated", "stroke"),
            ("sepsis bundle protocol", "sepsis"),
            ("trauma team activation", "trauma"),
            ("cardiac arrest response", "cardiac_arrest"),
            ("anaphylaxis treatment protocol", "anaphylaxis")
        ]
        
        for query, expected_protocol in test_cases:
            protocol = medical_metrics_collector.is_time_sensitive(query)
            assert protocol == expected_protocol
    
    def test_identify_urgent_keywords(self, medical_metrics_collector):
        """Test identification of general urgent keywords"""
        urgent_queries = [
            "STAT lab results needed",
            "urgent consultation required",
            "emergency medication needed",
            "critical patient status",
            "immediate intervention required"
        ]
        
        for query in urgent_queries:
            protocol = medical_metrics_collector.is_time_sensitive(query)
            assert protocol == "urgent_general"
    
    def test_identify_non_urgent(self, medical_metrics_collector):
        """Test non-urgent query identification"""
        routine_queries = [
            "routine medication review",
            "scheduled follow-up appointment",
            "elective procedure planning"
        ]
        
        for query in routine_queries:
            protocol = medical_metrics_collector.is_time_sensitive(query)
            assert protocol is None


class TestUrgencyLevelAssignment:
    """Test urgency level assignment"""
    
    def test_critical_urgency(self, medical_metrics_collector):
        """Test critical urgency assignment"""
        critical_queries = [
            "code blue activation",
            "cardiac arrest in progress",
            "critical patient deterioration",
            "emergency stat response"
        ]
        
        for query in critical_queries:
            urgency = medical_metrics_collector.get_urgency_level(query)
            assert urgency == "critical"
    
    def test_urgent_urgency(self, medical_metrics_collector):
        """Test urgent urgency assignment"""
        # Test with time-sensitive protocol
        urgency = medical_metrics_collector.get_urgency_level(
            "STEMI protocol needed", "STEMI"
        )
        assert urgency == "urgent"
        
        # Test with urgent keywords
        urgent_queries = [
            "urgent consultation needed",
            "immediate evaluation required",
            "rapid response needed"
        ]
        
        for query in urgent_queries:
            urgency = medical_metrics_collector.get_urgency_level(query)
            assert urgency == "urgent"
    
    def test_standard_urgency(self, medical_metrics_collector):
        """Test standard urgency assignment"""
        routine_queries = [
            "routine medication review",
            "scheduled procedure prep",
            "patient education materials"
        ]
        
        for query in routine_queries:
            urgency = medical_metrics_collector.get_urgency_level(query)
            assert urgency == "standard"


class TestMedicalAbbreviationDetection:
    """Test medical abbreviation detection"""
    
    def test_detect_common_abbreviations(self, medical_metrics_collector):
        """Test detection of common medical abbreviations"""
        test_cases = [
            ("patient has MI history", ["MI"]),
            ("CHF exacerbation protocol", ["CHF"]),
            ("COPD management guidelines", ["COPD"]),
            ("UTI treatment protocol", ["UTI"]),
            ("patient going to OR", ["OR"]),
            ("admit to ICU", ["ICU"])
        ]
        
        for query, expected_abbrs in test_cases:
            abbreviations = medical_metrics_collector.detect_medical_abbreviations(query)
            assert all(abbr in abbreviations for abbr in expected_abbrs)
    
    def test_detect_multiple_abbreviations(self, medical_metrics_collector):
        """Test detection of multiple abbreviations in one query"""
        query = "MI patient in ICU needs IV medication"
        
        abbreviations = medical_metrics_collector.detect_medical_abbreviations(query)
        
        expected_abbrs = ["MI", "ICU", "IV"]
        assert all(abbr in abbreviations for abbr in expected_abbrs)
    
    def test_detect_no_abbreviations(self, medical_metrics_collector):
        """Test queries with no medical abbreviations"""
        queries = [
            "patient feeling better today",
            "family visit scheduled",
            "discharge planning in progress"
        ]
        
        for query in queries:
            abbreviations = medical_metrics_collector.detect_medical_abbreviations(query)
            assert abbreviations == []
    
    def test_case_insensitive_detection(self, medical_metrics_collector):
        """Test case-insensitive abbreviation detection"""
        queries = [
            "mi protocol needed",
            "chf management",
            "copd exacerbation"
        ]
        
        for query in queries:
            abbreviations = medical_metrics_collector.detect_medical_abbreviations(query)
            assert len(abbreviations) > 0


class TestMedicalMetricsTracking:
    """Test medical metrics tracking"""
    
    def test_track_medical_query_basic(self, medical_metrics_collector):
        """Test basic medical query tracking"""
        with patch.multiple(
            'src.observability.medical_metrics',
            medical_queries_by_specialty=Mock(),
            clinical_confidence_distribution=Mock(),
            medical_abbreviation_usage=Mock()
        ) as mocks:
            
            # Configure mock returns
            for mock_metric in mocks.values():
                mock_metric.labels.return_value.inc = Mock()
                mock_metric.labels.return_value.observe = Mock()
            
            medical_metrics_collector.track_medical_query(
                query="chest pain protocol",
                query_type="PROTOCOL_STEPS",
                confidence=0.85,
                response_time=1.2
            )
            
            # Verify specialty tracking
            mocks['medical_queries_by_specialty'].labels.assert_called_with(
                specialty="cardiology",
                query_type="PROTOCOL_STEPS"
            )
            
            # Verify confidence tracking
            mocks['clinical_confidence_distribution'].labels.assert_called_with(
                clinical_area="cardiology"
            )
            mocks['clinical_confidence_distribution'].labels.return_value.observe.assert_called_with(0.85)
    
    def test_track_medical_query_disabled(self, disabled_medical_metrics_collector):
        """Test medical query tracking when disabled"""
        with patch('src.observability.medical_metrics.medical_queries_by_specialty') as mock_specialty:
            mock_specialty.labels.return_value.inc = Mock()
            
            disabled_medical_metrics_collector.track_medical_query(
                query="test query",
                query_type="PROTOCOL_STEPS", 
                confidence=0.8,
                response_time=1.0
            )
            
            # Should not call metrics when disabled
            mock_specialty.labels.assert_not_called()
    
    def test_track_time_sensitive_protocol(self, medical_metrics_collector):
        """Test time-sensitive protocol tracking"""
        with patch.multiple(
            'src.observability.medical_metrics',
            time_sensitive_protocols=Mock(),
            critical_protocol_access=Mock()
        ) as mocks:
            
            for mock_metric in mocks.values():
                mock_metric.labels.return_value.observe = Mock()
                mock_metric.labels.return_value.inc = Mock()
            
            with patch('src.observability.medical_metrics.datetime') as mock_datetime:
                # Mock daytime hour
                mock_datetime.now.return_value.hour = 14
                
                medical_metrics_collector.track_medical_query(
                    query="STEMI protocol needed",
                    query_type="PROTOCOL_STEPS",
                    confidence=0.9,
                    response_time=1.5
                )
            
            # Verify time-sensitive protocol tracking
            mocks['time_sensitive_protocols'].labels.assert_called_with(
                protocol_type="STEMI"
            )
            mocks['time_sensitive_protocols'].labels.return_value.observe.assert_called_with(1.5)
            
            # Verify critical protocol access tracking
            mocks['critical_protocol_access'].labels.assert_called_with(
                protocol="STEMI",
                time_of_day="day"
            )
    
    def test_track_medication_query(self, medical_metrics_collector):
        """Test medication query tracking"""
        with patch.multiple(
            'src.observability.medical_metrics',
            medication_dosage_queries=Mock(),
            dosage_safety_checks=Mock()
        ) as mocks:
            
            for mock_metric in mocks.values():
                mock_metric.labels.return_value.inc = Mock()
            
            medical_metrics_collector.track_medical_query(
                query="morphine 2mg IV for pain",
                query_type="DOSAGE_LOOKUP",
                confidence=0.88,
                response_time=0.8
            )
            
            # Verify medication tracking
            mocks['medication_dosage_queries'].labels.assert_called_with(
                medication="morphine",
                route="IV", 
                query_type="DOSAGE_LOOKUP"
            )
            
            # Verify safety checks for high-risk medication
            safety_call_args = [call.args for call in mocks['dosage_safety_checks'].labels.call_args_list]
            assert any("morphine" in str(args) for args in safety_call_args)
    
    def test_track_emergency_department_metrics(self, medical_metrics_collector):
        """Test emergency department metrics tracking"""
        with patch('src.observability.medical_metrics.emergency_department_metrics') as mock_ed:
            mock_ed.labels.return_value.inc = Mock()
            
            medical_metrics_collector.track_medical_query(
                query="trauma activation criteria",
                query_type="CRITERIA_CHECK",
                confidence=0.92,
                response_time=0.7
            )
            
            # Verify emergency department tracking
            mock_ed.labels.assert_called_with(
                urgency_level="urgent",
                query_category="criteria"
            )
            mock_ed.labels.return_value.inc.assert_called_once()
    
    def test_track_pharmacy_consultations(self, medical_metrics_collector):
        """Test pharmacy consultation tracking"""
        with patch('src.observability.medical_metrics.pharmacy_consultation_metrics') as mock_pharmacy:
            mock_pharmacy.labels.return_value.inc = Mock()
            
            medical_metrics_collector.track_medical_query(
                query="drug interaction between aspirin and warfarin",
                query_type="CRITERIA_CHECK",
                confidence=0.87,
                response_time=1.1
            )
            
            # Verify pharmacy consultation tracking
            mock_pharmacy.labels.assert_called_with(
                consultation_type="drug_interaction",
                medication_class="anticoagulant"
            )
            mock_pharmacy.labels.return_value.inc.assert_called_once()


class TestMedicalSafetyTracking:
    """Test medical safety event tracking"""
    
    def test_track_safety_event(self, medical_metrics_collector):
        """Test safety event tracking"""
        with patch('src.observability.medical_metrics.safety_alerts') as mock_alerts:
            mock_alerts.labels.return_value.inc = Mock()
            
            medical_metrics_collector.track_safety_event(
                event_type="medication_error",
                severity="high",
                details={"medication": "insulin", "error": "dosage"}
            )
            
            # Verify safety alert tracking
            mock_alerts.labels.assert_called_with(
                alert_type="medication_error",
                severity="high"
            )
            mock_alerts.labels.return_value.inc.assert_called_once()
    
    def test_update_protocol_adherence(self, medical_metrics_collector):
        """Test protocol adherence score updates"""
        with patch('src.observability.medical_metrics.protocol_adherence') as mock_adherence:
            mock_adherence.labels.return_value.set = Mock()
            
            medical_metrics_collector.update_protocol_adherence("STEMI", 0.95)
            
            mock_adherence.labels.assert_called_with(protocol_name="STEMI")
            mock_adherence.labels.return_value.set.assert_called_with(0.95)
    
    def test_track_clinical_decision_support(self, medical_metrics_collector):
        """Test clinical decision support tracking"""
        with patch('src.observability.medical_metrics.clinical_decision_support') as mock_cds:
            mock_cds.labels.return_value.inc = Mock()
            
            # Test high confidence decision
            medical_metrics_collector.track_clinical_decision_support("diagnosis", 0.88)
            
            mock_cds.labels.assert_called_with(
                decision_type="diagnosis",
                confidence_level="high"
            )
            
            # Test low confidence decision
            medical_metrics_collector.track_clinical_decision_support("treatment", 0.55)
            
            mock_cds.labels.assert_called_with(
                decision_type="treatment",
                confidence_level="low"
            )


class TestMedicalMetricsHelpers:
    """Test medical metrics helper methods"""
    
    def test_categorize_ed_query(self, medical_metrics_collector):
        """Test emergency department query categorization"""
        test_cases = [
            ("chest pain protocol steps", "protocol"),
            ("morphine dosage for pain", "medication"),
            ("STEMI criteria checklist", "criteria"),
            ("consent form for procedure", "documentation"),
            ("patient vital signs", "general")
        ]
        
        for query, expected_category in test_cases:
            category = medical_metrics_collector._categorize_ed_query(query)
            assert category == expected_category
    
    def test_categorize_pharmacy_query(self, medical_metrics_collector):
        """Test pharmacy query categorization"""
        test_cases = [
            ("drug interaction with warfarin", "drug_interaction"),
            ("morphine dosage calculation", "dosing"),
            ("aspirin side effects", "adverse_effects"),
            ("penicillin allergy reaction", "allergy"),
            ("medication storage requirements", "general")
        ]
        
        for query, expected_category in test_cases:
            category = medical_metrics_collector._categorize_pharmacy_query(query)
            assert category == expected_category
    
    def test_get_medication_class(self, medical_metrics_collector):
        """Test medication class determination"""
        test_cases = [
            ("penicillin allergy", "antibiotic"),
            ("morphine for pain control", "analgesic"),
            ("metoprolol for heart rate", "cardiac"),
            ("heparin anticoagulation", "anticoagulant"),
            ("albuterol inhaler", "respiratory"),
            ("vitamin supplement", "other")
        ]
        
        for query, expected_class in test_cases:
            med_class = medical_metrics_collector._get_medication_class(query)
            assert med_class == expected_class


class TestMedicalMetricsErrorHandling:
    """Test error handling in medical metrics"""
    
    def test_track_medical_query_with_exception(self, medical_metrics_collector):
        """Test graceful handling of exceptions in medical tracking"""
        with patch('src.observability.medical_metrics.medical_queries_by_specialty') as mock_specialty:
            mock_specialty.labels.side_effect = Exception("Metrics error")
            
            # Should not raise exception
            medical_metrics_collector.track_medical_query(
                query="test query",
                query_type="PROTOCOL_STEPS",
                confidence=0.8,
                response_time=1.0
            )
    
    def test_track_safety_event_with_exception(self, medical_metrics_collector):
        """Test safety event tracking with exception"""
        with patch('src.observability.medical_metrics.safety_alerts') as mock_alerts:
            mock_alerts.labels.side_effect = Exception("Safety tracking error")
            
            # Should handle exception gracefully
            medical_metrics_collector.track_safety_event(
                event_type="test_error",
                severity="low",
                details={}
            )


class TestMedicalMetricsIntegration:
    """Integration tests for medical metrics system"""
    
    def test_complete_medical_workflow_tracking(self, medical_metrics_collector):
        """Test complete medical workflow metrics"""
        with patch.multiple(
            'src.observability.medical_metrics',
            medical_queries_by_specialty=Mock(),
            clinical_confidence_distribution=Mock(),
            time_sensitive_protocols=Mock(),
            medication_dosage_queries=Mock(),
            medical_abbreviation_usage=Mock(),
            emergency_department_metrics=Mock()
        ) as mocks:
            
            # Configure all mocks
            for mock_metric in mocks.values():
                mock_metric.labels.return_value.inc = Mock()
                mock_metric.labels.return_value.observe = Mock()
            
            # Simulate complex medical query
            medical_metrics_collector.track_medical_query(
                query="STEMI protocol morphine 2mg IV for chest pain in ED",
                query_type="PROTOCOL_STEPS",
                confidence=0.92,
                response_time=1.3
            )
            
            # Verify multiple metrics were tracked
            assert mocks['medical_queries_by_specialty'].labels.called
            assert mocks['clinical_confidence_distribution'].labels.called
            assert mocks['time_sensitive_protocols'].labels.called
            assert mocks['medical_abbreviation_usage'].labels.called
            assert mocks['emergency_department_metrics'].labels.called
    
    def test_medical_metrics_initialization_integration(self, mock_settings):
        """Test complete medical metrics initialization"""
        with patch('src.observability.medical_metrics.medical_metrics') as mock_global:
            init_medical_metrics(mock_settings)
            
            assert mock_global.settings is mock_settings
            assert mock_global.enabled is True