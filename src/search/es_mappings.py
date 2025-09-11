"""Elasticsearch index mappings optimized for medical terminology."""

# Medical synonyms for better search accuracy
MEDICAL_SYNONYMS = [
    "MI,myocardial infarction,heart attack",
    "STEMI,ST elevation myocardial infarction",
    "NSTEMI,non ST elevation myocardial infarction", 
    "ED,emergency department,ER,emergency room",
    "BP,blood pressure",
    "HR,heart rate",
    "CPR,cardiopulmonary resuscitation",
    "ICU,intensive care unit",
    "CCU,cardiac care unit",
    "IV,intravenous",
    "IM,intramuscular",
    "PO,per os,by mouth,oral",
    "PRN,as needed,pro re nata",
    "BID,twice daily,twice a day",
    "TID,three times daily,three times a day",
    "QID,four times daily,four times a day",
    "EKG,ECG,electrocardiogram",
    "CT,computed tomography,CAT scan",
    "MRI,magnetic resonance imaging",
    "PE,pulmonary embolism",
    "DVT,deep vein thrombosis",
    "CHF,congestive heart failure,heart failure",
    "COPD,chronic obstructive pulmonary disease",
    "DKA,diabetic ketoacidosis",
    "GI,gastrointestinal",
    "UTI,urinary tract infection",
    "ACS,acute coronary syndrome",
    "TIA,transient ischemic attack,mini stroke",
    "CVA,cerebrovascular accident,stroke",
    "Code Blue,cardiac arrest,code",
    "ACLS,advanced cardiac life support",
    "BLS,basic life support",
    "PALS,pediatric advanced life support",
    "tPA,tissue plasminogen activator,alteplase"
]

DOCUMENT_INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "medical_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard",
                    "filter": ["lowercase", "medical_synonyms", "stop"]
                },
                "exact_match": {
                    "type": "keyword",
                    "normalizer": "lowercase"
                }
            },
            "normalizer": {
                "lowercase": {
                    "type": "custom",
                    "filter": ["lowercase"]
                }
            },
            "filter": {
                "medical_synonyms": {
                    "type": "synonym",
                    "synonyms": MEDICAL_SYNONYMS
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "content": {
                "type": "text",
                "analyzer": "medical_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "exact": {"type": "text", "analyzer": "standard"}
                }
            },
            "content_type": {"type": "keyword"},
            "filename": {
                "type": "text",
                "analyzer": "medical_analyzer",
                "fields": {"keyword": {"type": "keyword"}}
            },
            "title": {
                "type": "text",
                "analyzer": "medical_analyzer",
                "fields": {"keyword": {"type": "keyword"}}
            },
            "protocol_name": {"type": "keyword"},  # For exact protocol matching
            "form_name": {"type": "keyword"},      # For exact form matching
            "medical_specialties": {"type": "keyword"},
            "tags": {"type": "keyword"},
            "file_type": {"type": "keyword"},
            "file_hash": {"type": "keyword"},
            "metadata": {"type": "object", "enabled": False},  # Raw metadata storage
            "created_at": {"type": "date"},
            "updated_at": {"type": "date"}
        }
    }
}

CHUNK_INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "medical_analyzer": {
                    "type": "custom", 
                    "tokenizer": "standard",
                    "filter": ["lowercase", "medical_synonyms", "stop"]
                }
            },
            "filter": {
                "medical_synonyms": {
                    "type": "synonym",
                    "synonyms": MEDICAL_SYNONYMS
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "document_id": {"type": "keyword"},
            "content": {
                "type": "text",
                "analyzer": "medical_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"},
                    "exact": {"type": "text", "analyzer": "standard"}
                }
            },
            "chunk_index": {"type": "integer"},
            "chunk_type": {"type": "keyword"},
            "medical_category": {"type": "keyword"},
            "urgency_level": {"type": "keyword"},
            "contains_contact": {"type": "boolean"},
            "contains_dosage": {"type": "boolean"},
            "page_number": {"type": "integer"},
            "metadata": {"type": "object", "enabled": False},
            "created_at": {"type": "date"}
        }
    }
}

# Registry index for quick document lookup
REGISTRY_INDEX_MAPPING = {
    "settings": {
        "number_of_shards": 1,
        "number_of_replicas": 0,
        "analysis": {
            "analyzer": {
                "medical_analyzer": {
                    "type": "custom",
                    "tokenizer": "standard", 
                    "filter": ["lowercase", "medical_synonyms", "stop"]
                }
            },
            "filter": {
                "medical_synonyms": {
                    "type": "synonym",
                    "synonyms": MEDICAL_SYNONYMS
                }
            }
        }
    },
    "mappings": {
        "properties": {
            "id": {"type": "keyword"},
            "document_id": {"type": "keyword"},
            "keywords": {"type": "keyword"},
            "display_name": {
                "type": "text",
                "analyzer": "medical_analyzer",
                "fields": {"keyword": {"type": "keyword"}}
            },
            "file_path": {"type": "keyword"},
            "category": {"type": "keyword"},
            "priority": {"type": "integer"},
            "quick_access": {"type": "boolean"},
            "metadata": {"type": "object", "enabled": False}
        }
    }
}