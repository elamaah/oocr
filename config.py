"""Static configuration: prompts, currency tokens, category labels, rules.

No runtime logic here — only data tables that other modules import.
"""
from __future__ import annotations


# ──────────────────────────── LLM prompt ─────────────────────────────

SYSTEM_PROMPT = """You extract structured data from restaurant, pharmacy, grocery, and similar retail receipts in Arabic and English.

Rules:
- Output JSON conforming to the supplied schema. Nothing else.
- Copy values VERBATIM from the receipt as printed. Do not translate, reformat, or normalize.
- Dates and totals must be the exact substring as printed (e.g. "٠٥/١٢/٢٠٢٤", "12,50 ج.م"). Normalization happens downstream.
- If a field is absent, return null. Never invent values.
- Never sum, average, or compute totals — copy the printed total only.
- For each line item, return name and any of quantity/unit_price/total_price that are printed on that row. Use null for the rest.
- Read Arabic right-to-left as printed; preserve original digits (Arabic-Indic ٠١٢٣ or Western 0123) — do not transliterate.
- Pick exactly ONE category from the allowed list below. NEVER use a category not in the list — if the items don't clearly match anything, use "other". Match by item examples: if an item resembles one of the examples shown for a category, use that category.

{CATEGORY_GUIDE}

Inputs you may receive:
1. Always: a preprocessed image of the receipt. Read it directly.
2. Sometimes: extra OCR rows extracted by a local engine, one per line, tokens tab-separated, prefixed by row index. When provided, treat them as a hint for ambiguous digits — the image is still the primary source of truth."""


FEW_SHOT_EXAMPLES = """Example 1 — Arabic restaurant receipt:
OCR rows:
0\tمطعم الشام
1\tالتاريخ:\t٠٥/١٢/٢٠٢٤\t١٤:٣٠
2\tشاورما دجاج\t٢\t٤٥٫٠٠\t٩٠٫٠٠
3\tعصير برتقال\t١\t١٥٫٠٠\t١٥٫٠٠
4\tالاجمالي\t١٠٥٫٠٠ ج.م

Output:
{
  "date_raw": "٠٥/١٢/٢٠٢٤",
  "time_raw": "١٤:٣٠",
  "total_raw": "١٠٥٫٠٠ ج.م",
  "category": "restaurant",
  "items": [
    {"name": "شاورما دجاج", "quantity_raw": "٢", "unit_price_raw": "٤٥٫٠٠", "total_price_raw": "٩٠٫٠٠", "raw_line": "شاورما دجاج\\t٢\\t٤٥٫٠٠\\t٩٠٫٠٠"},
    {"name": "عصير برتقال", "quantity_raw": "١", "unit_price_raw": "١٥٫٠٠", "total_price_raw": "١٥٫٠٠", "raw_line": "عصير برتقال\\t١\\t١٥٫٠٠\\t١٥٫٠٠"}
  ]
}

Example 2 — English pharmacy receipt:
OCR rows:
0\tCity Pharmacy
1\t12/05/2024  10:15 AM
2\tParacetamol 500mg\tx2\t$3.50\t$7.00
3\tVitamin C\tx1\t$12.99\t$12.99
4\tTOTAL\t$19.99

Output:
{
  "date_raw": "12/05/2024",
  "time_raw": "10:15 AM",
  "total_raw": "$19.99",
  "category": "pharmacy",
  "items": [
    {"name": "Paracetamol 500mg", "quantity_raw": "x2", "unit_price_raw": "$3.50", "total_price_raw": "$7.00", "raw_line": "Paracetamol 500mg\\tx2\\t$3.50\\t$7.00"},
    {"name": "Vitamin C", "quantity_raw": "x1", "unit_price_raw": "$12.99", "total_price_raw": "$12.99", "raw_line": "Vitamin C\\tx1\\t$12.99\\t$12.99"}
  ]
}
"""


# ════════════════════ Category taxonomy (EDIT THIS) ════════════════════
#
# This is the single source of truth for categories. The LLM is constrained
# to pick exactly ONE of these keys. Add / remove / rename entries below and
# the prompt + schema validation update automatically — no other file needs
# to change.
#
# Each value is a list of EXAMPLE ITEMS that should map to that category.
# Mix Arabic and English freely. The model uses these examples as anchors:
# e.g. seeing "ice cream" or "ايس كريم" pushes it toward "restaurant".
#
# Always keep an "other" bucket as the last entry for items that genuinely
# don't fit anywhere else.

CATEGORY_TAXONOMY: dict[str, list[str]] = {
    "restaurant": [
"meals", "meal", "food", "foods", "dish", "dishes",
"shawarma", "burger", "hamburger", "cheeseburger",
"pizza", "rice", "kebab", "kofta", "grill", "bbq",
"chicken", "beef", "meat", "steak", "sausage",
"hotdog", "sandwich", "wrap", "sub", "toast",
"falafel", "taameya", "foul", "beans", "lentils",
"pasta", "spaghetti", "macaroni", "lasagna",
"noodles", "ramen", "fried rice", "biryani",
"mansaf", "kabsa", "maqluba", "molokhia",
"mahshi", "moussaka", "soup", "salad",
"caesar salad", "greek salad", "fattoush",
"tabbouleh", "hummus", "baba ghanoush",
"fries", "chips", "nuggets", "wings",
"fried chicken", "grilled chicken",
"fish", "seafood", "shrimp", "prawns",
"calamari", "sushi", "tempura",
"breakfast", "lunch", "dinner",
"snack", "combo", "family meal",
"kids meal", "box meal", "platter",
"dessert", "cake", "cookie", "donut",
"croissant", "muffin", "brownie",
"waffle", "pancake", "crepe",
"ice cream", "gelato", "sundae",
"milkshake", "smoothie",

"وجبة", "وجبات", "أكل", "طعام", "طبق",
"شاورما", "شاورما فراخ", "شاورما لحم",
"برجر", "هامبرجر", "تشيز برجر",
"بيتزا", "كباب", "كفتة", "أرز",
"رز", "مندي", "برياني", "كبسة",
"مقلوبة", "منسف", "ملوخية",
"محشي", "مسقعة", "طاجن",
"فراخ", "دجاج", "لحم", "لحمة",
"ستيك", "سجق", "هوت دوج",
"ساندوتش", "سندويتش", "راب",
"فلافل", "طعمية", "فول",
"عدس", "شوربة", "سلطة",
"فتوش", "تبولة", "حمص",
"بطاطس", "بطاطس مقلية",
"ناجتس", "أجنحة", "وينجز",
"فراخ مشوية", "فراخ مقلية",
"سمك", "مأكولات بحرية",
"جمبري", "كاليماري",
"سوشي", "نودلز", "مكرونة",
"سباجتي", "لازانيا",
"فطار", "إفطار",
"غدا", "غداء",
"عشا", "عشاء",
"سناك", "كومبو", "وجبة عائلية",
"وجبة أطفال", "بوكس وجبة",
"حلويات", "كيك", "بسكويت",
"دونات", "كرواسون", "مافن",
"براوني", "وافل", "بان كيك",
"كريب", "ايس كريم", "آيس كريم",
"جيلاتو", "ميلك شيك", "سموذي"
    ],
    "pharmacy": [
"medicine", "medicines", "drug", "drugs",
"medication", "medications",
"tablet", "tablets",
"pill", "pills",
"capsule", "capsules",
"syrup", "vitamin", "vitamins",
"prescription", "rx",
"antibiotic", "antibiotics",
"painkiller", "painkillers",
"analgesic", "antihistamine",
"antacid", "laxative",
"ointment", "cream", "gel",
"lotion", "spray",
"drops", "eye drops",
"ear drops", "nasal spray",
"inhaler", "insulin",
"injectable", "injection",
"vaccine", "supplement",
"minerals", "calcium",
"iron", "magnesium",
"zinc", "omega 3",
"probiotic", "protein",
"first aid", "bandage",
"gauze", "cotton",
"thermometer", "mask",
"gloves", "sanitizer",
"disinfectant", "antiseptic",
"mouthwash", "toothpaste",
"medical", "pharmacy",
"pharmaceutical",

"دواء", "أدوية",
"علاج", "علاجات",
"حبوب", "قرص", "أقراص",
"كبسولة", "كبسولات",
"شراب", "شرب",
"فيتامين", "فيتامينات",
"روشتة", "وصفة",
"مضاد حيوي", "مضادات حيوية",
"مسكن", "مسكنات",
"خافض حرارة",
"مضاد حساسية",
"مضاد حموضة",
"ملين",
"مرهم", "كريم",
"جل", "لوشن",
"بخاخ", "قطرة",
"قطرة عين",
"قطرة أذن",
"بخاخ أنف",
"أنسولين",
"حقنة", "حقن",
"لقاح",
"مكمل غذائي",
"مكملات غذائية",
"كالسيوم",
"حديد",
"ماغنسيوم",
"زنك",
"أوميجا",
"بروبيوتيك",
"بروتين",
"شاش", "قطن",
"ضمادة", "لاصق طبي",
"كمامة", "قفازات",
"مطهر", "معقم",
"غسول", "غسول فم",
"معجون أسنان",
"صيدلية",
"صيدليات",
"مستلزمات طبية",
"منتجات طبية",
"أجهزة طبية"
    ],
    "grocery": [
"bread", "milk", "vegetables", "vegetable",
"fruit", "fruits", "cheese", "eggs",
"yogurt", "butter", "cream",
"juice", "water", "mineral water",
"soft drink", "cola", "soda",
"tea", "coffee", "sugar",
"salt", "rice", "pasta",
"spaghetti", "flour", "oil",
"sunflower oil", "olive oil",
"ghee", "jam", "honey",
"chocolate", "candy", "biscuits",
"cookies", "chips", "snacks",
"nuts", "dates", "raisins",
"beans", "lentils", "peas",
"corn", "tuna", "sardines",
"frozen food", "frozen vegetables",
"chicken", "beef", "meat",
"fish", "shrimp",
"apple", "banana", "orange",
"mango", "grapes", "watermelon",
"tomato", "potato", "onion",
"cucumber", "pepper", "carrot",
"garlic", "lettuce",
"detergent", "soap",
"shampoo", "toothpaste",
"tissue", "paper towels",
"cleaner", "bleach",
"household", "grocery",
"supermarket", "market",

"خبز", "عيش", "حليب",
"لبن", "خضار", "فواكه",
"جبن", "بيض", "زبادي",
"زبادي", "زبدة", "قشطة",
"عصير", "مياه", "مياه معدنية",
"مشروب غازي", "كولا",
"شاي", "قهوة",
"سكر", "ملح",
"أرز", "رز",
"مكرونة", "دقيق",
"زيت", "زيت ذرة",
"زيت عباد الشمس",
"زيت زيتون",
"سمن", "مربى",
"عسل", "شوكولاتة",
"حلويات", "بسكويت",
"شيبسي", "سناكس",
"مكسرات", "تمر",
"زبيب", "فول",
"عدس", "بازلاء",
"ذرة", "تونة",
"سردين",
"مجمدات", "خضار مجمدة",
"فراخ", "دجاج",
"لحم", "لحمة",
"سمك", "جمبري",
"تفاح", "موز",
"برتقال", "مانجو",
"عنب", "بطيخ",
"طماطم", "بطاطس",
"بصل", "خيار",
"فلفل", "جزر",
"ثوم", "خس",
"منظف", "مسحوق",
"صابون", "شامبو",
"معجون أسنان",
"مناديل", "كلور",
"مطهر", "منظفات",
"بقالة", "سوبر ماركت",
"هايبر ماركت", "ماركت"
    ],
    "cafe": [
"coffee", "tea", "espresso", "latte", "cappuccino", "americano",
"mocha", "macchiato", "flat white", "cold brew", "iced coffee",
"frappe", "frappuccino", "espresso shot",
"cafe", "café", "coffee shop", "beverage", "drinks",

"pastry", "cake", "dessert", "croissant", "muffin",
"donut", "cookie", "brownie", "waffle", "pancake",
"pie", "tart", "cheesecake", "cupcake", "biscuit",
"scone", "danish", "baklava",

"قهوة", "شاي", "كابتشينو", "لاتيه", "اسبريسو",
"موكا", "ماكياتو", "فلات وايت", "كولد برو",
"قهوة مثلجة", "قهوة باردة",
"فرابتشينو", "فرابيه",
"كافيه", "مشروبات", "مشروب ساخن", "مشروبات ساخنة",

"حلويات", "حلوى", "تحلية", "تحليات",
"كيك", "جاتوه", "تورتة",
"كرواسون", "مافن", "دونات",
"كوكيز", "براوني", "وافل",
"بان كيك", "فطيرة", "تارت", "تشيز كيك",
"بسكويت", "سكون", "دانش", "بقلاوة"
    ],
    "fuel": [
"gasoline", "petrol", "diesel", "fuel", "liters", "litre", "liter",
"octane", "fuel oil", "gas oil",
"unleaded", "super", "premium", "regular",
"vehicle fuel", "car fuel", "refuel", "fuel station",
"gas station", "service station", "filling station",

"بنزين", "سولار", "ديزل", "وقود", "لتر", "لترات",
"بنزين 80", "بنزين 92", "بنزين 95",
"مازوت", "غاز", "غاز طبيعي",
"محطة بنزين", "طلمبة بنزين", "تموين",
"تعبيه بنزين", "تفويل", "تموين سيارات",
"وقود سيارات", "وقود مركبات"
    ],
    "electronics": [
"phone", "smartphone", "mobile", "cellphone", "cell phone",
"laptop", "notebook", "ultrabook", "macbook",
"tablet", "ipad", "pc", "computer", "desktop",
"headphones", "earphones", "earbuds", "airpods",
"charger", "fast charger", "wireless charger", "power adapter",
"cable", "usb cable", "type c", "usb-c", "lightning cable",
"adapter", "power bank", "battery", "batteries",
"speaker", "bluetooth speaker", "sound system",
"microphone", "webcam", "router", "modem",
"memory card", "sd card", "flash drive", "usb flash",
"hard drive", "ssd", "hdd",

"هاتف", "موبايل", "موبيل", "تليفون", "جوال",
"لابتوب", "كمبيوتر", "حاسب", "كمبيوتر محمول",
"تابلت", "آيباد",
"سماعات", "هيدفون", "إيربودز", "سماعة بلوتوث",
"شاحن", "شاحن سريع", "شاحن لاسلكي",
"كابل", "سلك", "وصلة", "يو إس بي", "تايب سي",
"باور بانك", "بطارية", "سماعة", "مكبر صوت",
"راوتر", "مودم",
"فلاشة", "كارت ميموري", "هارد", "اس اس دي"
    ],
    "clothing": [
"shirt", "t-shirt", "tee", "polo", "blouse",
"pants", "trousers", "jeans", "denim", "shorts",
"dress", "gown", "skirt", "mini skirt", "maxi dress",
"shoes", "sneakers", "sneaker", "boots", "sandals",
"slippers", "heels", "high heels", "loafers", "flip flops",
"jacket", "coat", "hoodie", "sweater", "jumper",
"suit", "tie", "belt", "sock", "socks",
"underwear", "boxers", "bra",

"قميص", "تيشيرت", "بلوزة", "بولو",
"بنطلون", "جينز", "شورت", "دنيم",
"فستان", "جيبة", "تنورة", "فستان طويل", "فستان قصير",
"حذاء", "جزمة", "كوتشي", "سنيكرز", "صندل",
"شبشب", "كعب", "حذاء بكعب عالي",
"جاكيت", "معطف", "هودي", "بلوفر", "سويت شيرت",
"بدلة", "كرافته", "ربطة عنق", "حزام", "شراب",
"ملابس داخلية", "بوكسر", "حمالة صدر"
    ],
    "other": [],
}

CATEGORIES: list[str] = list(CATEGORY_TAXONOMY.keys())


def _format_taxonomy_for_prompt() -> str:
    """Render CATEGORY_TAXONOMY into the chunk we inject into the system prompt."""
    lines = ["Allowed categories (pick exactly ONE — never invent a new one):"]
    for name, examples in CATEGORY_TAXONOMY.items():
        if examples:
            preview = ", ".join(examples[:8])
            lines.append(f'  - "{name}": e.g. {preview}')
        else:
            lines.append(f'  - "{name}": fallback when nothing else fits')
    return "\n".join(lines)


CATEGORY_PROMPT_BLOCK = _format_taxonomy_for_prompt()

# Substitute the {CATEGORY_GUIDE} placeholder in SYSTEM_PROMPT now that the
# block is built. (SYSTEM_PROMPT is defined earlier; we patch it here so
# the editable taxonomy can drive the prompt.)
SYSTEM_PROMPT = SYSTEM_PROMPT.replace("{CATEGORY_GUIDE}", CATEGORY_PROMPT_BLOCK)


# Hard rules — applied as a final override when keyword evidence is unambiguous.
# Maps a substring (lowercased) to a category. Checked against merchant name and item names.
CATEGORY_RULES: list[tuple[str, str]] = [
    ("بنزين", "fuel"),
    ("سولار", "fuel"),
    ("ديزل", "fuel"),
    ("petrol", "fuel"),
    ("diesel", "fuel"),
    ("gasoline", "fuel"),
    ("صيدلية", "pharmacy"),
    ("صيدليه", "pharmacy"),
    ("pharmacy", "pharmacy"),
    ("drug store", "pharmacy"),
    ("مطعم", "restaurant"),
    ("restaurant", "restaurant"),
    ("كافيه", "cafe"),
    ("كافي", "cafe"),
    ("coffee", "cafe"),
    ("cafe", "cafe"),
    ("café", "cafe"),
    ("سوبر ماركت", "grocery"),
    ("بقالة", "grocery"),
    ("supermarket", "grocery"),
    ("grocery", "grocery"),
    ("hyper", "grocery"),
]


# ──────────────────────── Digit translation tables ────────────────────────

# Arabic-Indic digits → ASCII
ARABIC_INDIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
# Persian/Eastern Arabic digits → ASCII
PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
# Arabic decimal separator (٫ U+066B) → period
ARABIC_DECIMAL = str.maketrans("٫", ".")
# Arabic thousands separator (٬ U+066C) → comma
ARABIC_THOUSANDS = str.maketrans("٬", ",")
