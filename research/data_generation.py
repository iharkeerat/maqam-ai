"""Build a clearly labelled multilingual synthetic seed benchmark.

The seed benchmark exists to exercise the complete ML/evaluation pipeline before
expert annotations are available. It must never be described as expert validation.
"""
from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

LANGUAGE_BANKS: dict[str, dict[str, list[str]]] = {
    "Roman": {
        "karuna": ["dard remains after the footsteps fade", "the waiting heart counts a silent night", "memory returns with rain in the eyes"],
        "bhakti": ["the seeker repeats the sacred name", "prayer becomes breath and breath becomes light", "the self bows before an unseen truth"],
        "shringara": ["the beloved arrives through fragrance and moonlight", "love hides in the pause between two words", "the glance of the beloved unsettles the heart"],
        "shanta": ["silence opens like a clear river", "the restless mind settles at dawn", "peace remains when every name dissolves"],
        "vira": ["courage rises before the final drum", "the steadfast heart refuses to retreat", "victory is carried without pride"],
        "raudra": ["anger burns through the broken promise", "the sky answers injustice with fire", "the wounded voice becomes thunder"],
        "adbhuta": ["wonder appears where the ordinary world opens", "a hidden star turns the night into mystery", "the impossible blooms without warning"],
        "bhayanaka": ["fear follows the traveller through darkness", "an empty road listens behind every step", "the night holds an unnamed danger"],
        "bibhatsa": ["the heart recoils from deceit and cruelty", "false splendour leaves only disgust", "the corrupted feast turns the spirit away"],
    },
    "Hindi": {
        "karuna": ["दर्द पगचिह्न मिटने के बाद भी ठहरा है", "प्रतीक्षा करता हृदय मौन रात गिनता है", "स्मृति आँखों में सावन बनकर लौटती है"],
        "bhakti": ["साधक पवित्र नाम को साँसों में दोहराता है", "प्रार्थना प्रकाश बनकर भीतर उतरती है", "अहंकार अनदेखे सत्य के आगे झुकता है"],
        "shringara": ["प्रिय की आहट चाँदनी और सुगंध में आती है", "दो शब्दों के विराम में प्रेम छिपा है", "प्रिय की एक दृष्टि हृदय को व्याकुल करती है"],
        "shanta": ["मौन निर्मल नदी की तरह खुलता है", "भोर में चंचल मन शांत हो जाता है", "हर नाम मिटने पर शांति शेष रहती है"],
        "vira": ["अंतिम नगाड़े से पहले साहस उठता है", "अडिग हृदय पीछे हटने से इनकार करता है", "विजय बिना अभिमान के धारण की जाती है"],
        "raudra": ["टूटे वचन पर क्रोध अग्नि बनता है", "अन्याय का उत्तर आकाश ज्वाला से देता है", "घायल स्वर गर्जना बन जाता है"],
        "adbhuta": ["साधारण जगत के खुलते ही विस्मय जन्मता है", "छिपा तारा रात को रहस्य बना देता है", "असंभव बिना सूचना के खिल उठता है"],
        "bhayanaka": ["अँधेरे में भय यात्री के पीछे चलता है", "सूनी राह हर कदम के पीछे सुनती है", "रात अनाम संकट को थामे रहती है"],
        "bibhatsa": ["कपट और क्रूरता से हृदय घृणा करता है", "झूठा वैभव केवल वितृष्णा छोड़ता है", "भ्रष्ट उत्सव से आत्मा मुँह मोड़ती है"],
    },
    "Punjabi": {
        "karuna": ["ਪੈਰਾਂ ਦੇ ਨਿਸ਼ਾਨ ਮਿਟੇ ਪਰ ਦਰਦ ਰਹਿ ਗਿਆ", "ਉਡੀਕਦਾ ਦਿਲ ਚੁੱਪ ਰਾਤਾਂ ਗਿਣਦਾ ਹੈ", "ਯਾਦ ਅੱਖਾਂ ਵਿੱਚ ਸਾਵਣ ਬਣ ਕੇ ਮੁੜਦੀ ਹੈ"],
        "bhakti": ["ਸਾਧਕ ਪਵਿੱਤਰ ਨਾਮ ਨੂੰ ਸਾਹਾਂ ਵਿੱਚ ਜਪਦਾ ਹੈ", "ਅਰਦਾਸ ਅੰਦਰ ਰੌਸ਼ਨੀ ਬਣ ਕੇ ਉਤਰਦੀ ਹੈ", "ਹਉਮੈ ਅਣਦੇਖੇ ਸੱਚ ਅੱਗੇ ਝੁਕਦੀ ਹੈ"],
        "shringara": ["ਮਾਹੀ ਦੀ ਆਹਟ ਚਾਨਣ ਤੇ ਮਹਿਕ ਵਿੱਚ ਆਉਂਦੀ ਹੈ", "ਦੋ ਬੋਲਾਂ ਦੇ ਵਿਚਕਾਰ ਇਸ਼ਕ ਲੁਕਿਆ ਹੈ", "ਸੱਜਣ ਦੀ ਨਜ਼ਰ ਦਿਲ ਨੂੰ ਬੇਚੈਨ ਕਰਦੀ ਹੈ"],
        "shanta": ["ਚੁੱਪ ਨਿਰਮਲ ਦਰਿਆ ਵਾਂਗ ਖੁਲਦੀ ਹੈ", "ਸਵੇਰ ਨੂੰ ਭਟਕਦਾ ਮਨ ਟਿਕ ਜਾਂਦਾ ਹੈ", "ਹਰ ਨਾਮ ਮਿਟੇ ਤਾਂ ਸਕੂਨ ਰਹਿ ਜਾਂਦਾ ਹੈ"],
        "vira": ["ਆਖਰੀ ਨਗਾਰੇ ਤੋਂ ਪਹਿਲਾਂ ਹਿੰਮਤ ਉੱਠਦੀ ਹੈ", "ਅਡੋਲ ਦਿਲ ਪਿੱਛੇ ਹਟਣ ਤੋਂ ਇਨਕਾਰ ਕਰਦਾ ਹੈ", "ਜਿੱਤ ਬਿਨਾ ਘਮੰਡ ਦੇ ਧਾਰੀ ਜਾਂਦੀ ਹੈ"],
        "raudra": ["ਟੁੱਟੇ ਵਾਅਦੇ ਉੱਤੇ ਗੁੱਸਾ ਅੱਗ ਬਣਦਾ ਹੈ", "ਅਨਿਆਇ ਨੂੰ ਅਸਮਾਨ ਜਵਾਲਾ ਨਾਲ ਜਵਾਬ ਦਿੰਦਾ ਹੈ", "ਜ਼ਖ਼ਮੀ ਆਵਾਜ਼ ਗਰਜ ਬਣ ਜਾਂਦੀ ਹੈ"],
        "adbhuta": ["ਸਧਾਰਨ ਜਹਾਨ ਖੁਲਦਾ ਹੈ ਤੇ ਵਿਸਮਾਦ ਜੰਮਦਾ ਹੈ", "ਲੁਕਿਆ ਤਾਰਾ ਰਾਤ ਨੂੰ ਰਾਜ਼ ਬਣਾਉਂਦਾ ਹੈ", "ਅਸੰਭਵ ਅਚਾਨਕ ਖਿੜ ਪੈਂਦਾ ਹੈ"],
        "bhayanaka": ["ਹਨੇਰੇ ਵਿੱਚ ਡਰ ਮੁਸਾਫ਼ਰ ਦੇ ਪਿੱਛੇ ਤੁਰਦਾ ਹੈ", "ਸੁੰਨੀ ਰਾਹ ਹਰ ਕਦਮ ਪਿੱਛੇ ਸੁਣਦੀ ਹੈ", "ਰਾਤ ਅਣਜਾਣ ਖ਼ਤਰਾ ਫੜੀ ਬੈਠੀ ਹੈ"],
        "bibhatsa": ["ਧੋਖੇ ਤੇ ਜ਼ੁਲਮ ਤੋਂ ਦਿਲ ਘਿਣ ਕਰਦਾ ਹੈ", "ਝੂਠੀ ਸ਼ਾਨ ਸਿਰਫ਼ ਨਫ਼ਰਤ ਛੱਡਦੀ ਹੈ", "ਭ੍ਰਿਸ਼ਟ ਮੇਲੇ ਤੋਂ ਰੂਹ ਮੂੰਹ ਮੋੜਦੀ ਹੈ"],
    },
    "Urdu": {
        "karuna": ["نقش مٹ گئے مگر درد باقی رہا", "منتظر دل خاموش راتیں گنتا ہے", "یاد آنکھوں میں ساون بن کر لوٹتی ہے"],
        "bhakti": ["طالب مقدس نام کو سانسوں میں دہراتا ہے", "دعا اندر روشنی بن کر اترتی ہے", "خودی ان دیکھے حق کے آگے جھکتی ہے"],
        "shringara": ["محبوب کی آہٹ چاندنی اور خوشبو میں آتی ہے", "دو لفظوں کے وقفے میں عشق چھپا ہے", "یار کی ایک نظر دل کو بے قرار کرتی ہے"],
        "shanta": ["خاموشی صاف دریا کی طرح کھلتی ہے", "صبح بے قرار دل کو سکون دیتی ہے", "ہر نام مٹ جائے تو امن باقی رہتا ہے"],
        "vira": ["آخری نقارے سے پہلے ہمت اٹھتی ہے", "ثابت قدم دل پیچھے ہٹنے سے انکار کرتا ہے", "فتح کو غرور کے بغیر اٹھایا جاتا ہے"],
        "raudra": ["ٹوٹے وعدے پر غصہ آگ بن جاتا ہے", "ظلم کا جواب آسمان شعلے سے دیتا ہے", "زخمی آواز گرج بن جاتی ہے"],
        "adbhuta": ["معمولی دنیا کھلے تو حیرت جنم لیتی ہے", "چھپا ستارہ رات کو راز بنا دیتا ہے", "ناممکن اچانک کھل اٹھتا ہے"],
        "bhayanaka": ["اندھیرے میں خوف مسافر کے پیچھے چلتا ہے", "سنسان راہ ہر قدم کے پیچھے سنتی ہے", "رات ایک بے نام خطرہ تھامے رہتی ہے"],
        "bibhatsa": ["فریب اور ظلم سے دل نفرت کرتا ہے", "جھوٹی شان صرف کراہت چھوڑتی ہے", "بدعنوان جشن سے روح منہ موڑتی ہے"],
    },
}

TIME_BANK = {
    "morning": {"Roman": "at the first light of morning", "Hindi": "प्रभात की पहली रोशनी में", "Punjabi": "ਸਵੇਰ ਦੀ ਪਹਿਲੀ ਲੋਅ ਵਿੱਚ", "Urdu": "صبح کی پہلی روشنی میں"},
    "afternoon": {"Roman": "under the still afternoon sun", "Hindi": "स्थिर दोपहर की धूप में", "Punjabi": "ਥਿਰ ਦੁਪਹਿਰ ਦੀ ਧੁੱਪ ਹੇਠ", "Urdu": "ٹھہری دوپہر کی دھوپ میں"},
    "evening": {"Roman": "as evening gathers at the threshold", "Hindi": "जब संध्या देहरी पर उतरती है", "Punjabi": "ਜਦ ਸ਼ਾਮ ਦੇਹਲੀਜ਼ ਉੱਤੇ ਉਤਰਦੀ ਹੈ", "Urdu": "جب شام دہلیز پر اترتی ہے"},
    "night": {"Roman": "through the deep listening night", "Hindi": "गहरी सुनती हुई रात में", "Punjabi": "ਗਹਿਰੀ ਸੁਣਦੀ ਰਾਤ ਵਿੱਚ", "Urdu": "گہری سنتی ہوئی رات میں"},
    "flexible": {"Roman": "beyond the boundary of clock and season", "Hindi": "घड़ी और ऋतु की सीमा से परे", "Punjabi": "ਘੜੀ ਤੇ ਰੁੱਤ ਦੀ ਹੱਦ ਤੋਂ ਪਰੇ", "Urdu": "وقت اور موسم کی حد سے پرے"},
}

FORM_BANK = {
    "Khayal": {"Roman": "the thought unfolds slowly", "Hindi": "विचार धीरे-धीरे विस्तार लेता है", "Punjabi": "ਖ਼ਿਆਲ ਹੌਲੇ ਹੌਲੇ ਖੁਲਦਾ ਹੈ", "Urdu": "خیال آہستہ آہستہ کھلتا ہے"},
    "Bandish": {"Roman": "the refrain returns to its resting word", "Hindi": "मुखड़ा अपने ठहराव शब्द पर लौटता है", "Punjabi": "ਮੁਖੜਾ ਆਪਣੇ ਠਹਿਰਾਉ ਵਾਲੇ ਬੋਲ ਵੱਲ ਮੁੜਦਾ ਹੈ", "Urdu": "مکھڑا اپنے ٹھہراؤ کے لفظ پر لوٹتا ہے"},
    "Thumri": {"Roman": "the phrase bends toward intimate longing", "Hindi": "पंक्ति अंतरंग विरह की ओर मुड़ती है", "Punjabi": "ਪੰਕਤੀ ਅੰਦਰਲੇ ਵਿਛੋੜੇ ਵੱਲ ਮੁੜਦੀ ਹੈ", "Urdu": "مصرع باطنی ہجر کی طرف مڑتا ہے"},
    "Ghazal": {"Roman": "each line keeps a private wound", "Hindi": "हर पंक्ति एक निजी घाव सँभालती है", "Punjabi": "ਹਰ ਪੰਕਤੀ ਆਪਣਾ ਜ਼ਖ਼ਮ ਸੰਭਾਲਦੀ ਹੈ", "Urdu": "ہر مصرع اپنا ایک زخم سنبھالتا ہے"},
    "Bhajan": {"Roman": "the refrain becomes remembrance", "Hindi": "मुखड़ा स्मरण बन जाता है", "Punjabi": "ਮੁਖੜਾ ਸਿਮਰਨ ਬਣ ਜਾਂਦਾ ਹੈ", "Urdu": "مکھڑا یادِ حق بن جاتا ہے"},
    "Dadra": {"Roman": "the short cycle carries a tender turn", "Hindi": "छोटा चक्र कोमल मोड़ सँभालता है", "Punjabi": "ਛੋਟਾ ਚੱਕਰ ਕੋਮਲ ਮੋੜ ਲੈ ਜਾਂਦਾ ਹੈ", "Urdu": "مختصر چکر نرم موڑ کو اٹھاتا ہے"},
    "Folk": {"Roman": "the line moves with an open communal pulse", "Hindi": "पंक्ति लोक की खुली चाल में चलती है", "Punjabi": "ਪੰਕਤੀ ਲੋਕੀ ਖੁੱਲ੍ਹੀ ਚਾਲ ਵਿੱਚ ਤੁਰਦੀ ਹੈ", "Urdu": "مصرع عوامی کھلی لے میں چلتا ہے"},
    "Light classical": {"Roman": "the melody keeps room for direct expression", "Hindi": "धुन सीधे भाव के लिए जगह रखती है", "Punjabi": "ਧੁਨ ਸਿੱਧੇ ਭਾਵ ਲਈ ਥਾਂ ਰੱਖਦੀ ਹੈ", "Urdu": "دھن براہِ راست اظہار کے لیے جگہ رکھتی ہے"},
}

RASA_ALIASES = {
    "karuna": ["karuna", "virah", "vairagya", "anxiety", "samarpan"],
    "bhakti": ["bhakti", "prarthana", "adhyatma", "spiritual"],
    "shringara": ["shringar", "love", "chanchal"],
    "shanta": ["shanta", "shanti", "prasannata", "ananda", "gambhir"],
    "vira": ["veer", "shahi"],
    "raudra": ["raudra"],
    "adbhuta": ["adbhuta", "wonder"],
    "bhayanaka": ["bhayanaka", "fear"],
    "bibhatsa": ["bibhatsa", "disgust"],
}


@dataclass(frozen=True)
class SeedRow:
    item_id: str
    split: str
    language: str
    poem: str
    primary_raag: str
    accepted_raags: str
    primary_taal: str
    accepted_taals: str
    form: str
    time_hint: str
    template_family: str
    is_synthetic: str = "true"
    provenance: str = "maqam-seed-template-generator-v1"


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def _primary_rasa(record: dict[str, object]) -> str:
    value = str(record.get("primaryRasa") or record.get("prakriti") or "shanta").casefold()
    for rasa, aliases in RASA_ALIASES.items():
        if any(alias in value for alias in aliases):
            return rasa
    return "shanta"


def _time_bucket(value: str) -> str:
    lowered = value.casefold()
    if any(token in lowered for token in ["morning", "dawn"]):
        return "morning"
    if any(token in lowered for token in ["afternoon", "noon"]):
        return "afternoon"
    if any(token in lowered for token in ["evening", "sunset", "sandhi"]):
        return "evening"
    if any(token in lowered for token in ["night", "midnight"]):
        return "night"
    return "flexible"


def _similar_raags(records: list[dict[str, object]], current: dict[str, object], limit: int = 2) -> list[str]:
    vector = [float(v) for v in current.get("rasaVector", [])]
    time_bucket = _time_bucket(str(current.get("time", "")))
    scored: list[tuple[float, str]] = []
    for other in records:
        if other["id"] == current["id"]:
            continue
        other_vector = [float(v) for v in other.get("rasaVector", [])]
        dot = sum(a * b for a, b in zip(vector, other_vector))
        aa = sum(a * a for a in vector) ** 0.5
        bb = sum(b * b for b in other_vector) ** 0.5
        cosine = dot / (aa * bb) if aa and bb else 0.0
        time_bonus = 0.08 if _time_bucket(str(other.get("time", ""))) == time_bucket else 0.0
        scored.append((cosine + time_bonus, str(other["id"])))
    return [raag_id for _, raag_id in sorted(scored, reverse=True)[:limit]]


def build_seed_rows(raag_records: list[dict[str, object]], seed: int = 20260730) -> list[SeedRow]:
    rng = random.Random(seed)
    rows: list[SeedRow] = []
    family_splits = {0: "train", 1: "train", 2: "train", 3: "train", 4: "dev", 5: "test"}
    for record in raag_records:
        rasa = _primary_rasa(record)
        time_bucket = _time_bucket(str(record.get("time", "")))
        forms = [str(v) for v in record.get("recommendedForms", [])] or ["Khayal"]
        taals = [str(v) for v in record.get("recommendedTaals", [])] or ["Teentaal"]
        alternatives = _similar_raags(raag_records, record)
        accepted_raags = ";".join([str(record["id"]), *alternatives])
        accepted_taals = ";".join(taals[:3])
        for language, banks in LANGUAGE_BANKS.items():
            phrases = banks[rasa]
            for family_index in range(6):
                split = family_splits[family_index]
                form = forms[family_index % len(forms)]
                phrase_a = phrases[family_index % len(phrases)]
                phrase_b = phrases[(family_index + 1) % len(phrases)]
                time_phrase = TIME_BANK[time_bucket][language]
                form_phrase = FORM_BANK.get(form, FORM_BANK["Khayal"])[language]
                context = str(record.get("contextLogic") or record.get("prakriti") or "").strip()
                context = re.sub(r"\b(?:raag|raga)\b", "", context, flags=re.I).strip(" .")
                options = [
                    f"{phrase_a}; {time_phrase}.\n{phrase_b}; {form_phrase}.",
                    f"{time_phrase}, {phrase_a}.\n{form_phrase}; {phrase_b}.",
                    f"{phrase_b}. {time_phrase}.\n{phrase_a}; {form_phrase}.",
                ]
                poem = options[family_index % len(options)]
                # Context is kept only in training families so test evaluation is not
                # trivially recoverable from record-specific prose.
                if split == "train" and context and family_index % 2 == 0:
                    poem += f"\n{context}."
                digest = hashlib.sha1(f"{record['id']}|{language}|{family_index}".encode()).hexdigest()[:10]
                rows.append(SeedRow(
                    item_id=f"syn-{_slug(str(record['id']))}-{digest}",
                    split=split,
                    language=language,
                    poem=poem,
                    primary_raag=str(record["id"]),
                    accepted_raags=accepted_raags,
                    primary_taal=taals[0],
                    accepted_taals=accepted_taals,
                    form=form,
                    time_hint=time_bucket,
                    template_family=f"{language.casefold()}-family-{family_index}",
                ))
    rng.shuffle(rows)
    return rows


def write_csv(rows: Iterable[SeedRow], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(SeedRow.__dataclass_fields__)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.__dict__)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    records = json.loads((root / "web/app/data/raag_seed.json").read_text(encoding="utf-8"))
    rows = build_seed_rows(records)
    output = root / "evaluation/seed_benchmark_v1.csv"
    write_csv(rows, output)
    counts = {split: sum(row.split == split for row in rows) for split in ["train", "dev", "test"]}
    print(json.dumps({"output": str(output), "rows": len(rows), "splits": counts, "synthetic": True}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
