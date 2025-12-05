import json
from jsonschema import validate, Draft202012Validator
from app.models import Profile

OUTPUT_JSON_SCHEMA = {
  "type":"object",
  "required":["resume","cover_letter","ats"],
  "properties":{
    "resume":{
      "type":"object",
      "required":["summary","skills_line","experience","projects","education"],
      "properties":{
        "summary":{"type":"string"},
        "skills_line":{"type":"array","items":{"type":"string"}},
        "experience":{"type":"array","items":{
          "type":"object",
          "required":["title","company","bullets"],
          "properties":{
            "title":{"type":"string"},
            "company":{"type":"string"},
            "start":{"type":"string"},
            "end":{"type":"string"},
            "bullets":{"type":"array","items":{"type":"string"}}
          }
        }},
        "projects":{"type":"array"},
        "education":{"type":"array"}
      }
    },
    "cover_letter":{
      "type":"object",
      "required":["address","intro","why_you","evidence","why_them","close"],
      "properties":{
        "address":{"type":"string"},
        "intro":{"type":"string"},
        "why_you":{"type":"string"},
        "evidence":{"type":"array","items":{"type":"string"}},
        "why_them":{"type":"string"},
        "close":{"type":"string"}
      }
    },
    "ats":{
      "type":"object",
      "required":["jd_keywords_matched","risks"],
      "properties":{
        "jd_keywords_matched":{"type":"array","items":{"type":"string"}},
        "risks":{"type":"array","items":{"type":"string"}}
      }
    }
  }
}

def validate_or_error(raw_json:str)->dict:
    try:
        data = json.loads(raw_json)
    except Exception as e:
        raise ValueError(f"Invalid JSON: {e}")
    errors = sorted(Draft202012Validator(OUTPUT_JSON_SCHEMA).iter_errors(data), key=lambda e: e.path)
    if errors:
        raise ValueError("Schema errors: " + "; ".join([e.message for e in errors]))
    return data

def business_rules_check(data:dict, profile:Profile):
    # company/title safety: must be subset of profile companies (or blank)
    prof_companies = {r.company for r in profile.experience}
    for r in data["resume"]["experience"]:
        if r["company"] and r["company"] not in prof_companies:
            raise ValueError(f"company not in profile: {r['company']}")
