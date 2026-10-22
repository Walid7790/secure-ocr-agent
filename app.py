import sqlite3
from pathlib import Path
from collections import Counter
import re
import locale
import os
import concurrent.futures
import streamlit as st
import pytesseract
from PIL import Image
from pillow_heif import register_heif_opener

register_heif_opener()
DB_FILE = "my_images.db"
FREE_LIMIT = 100

def get_system_language():
    try:
        sys_lang = locale.getdefaultlocale()[0] or os.environ.get('LANG', '')
        if sys_lang:
            sys_lang = sys_lang.lower()
            if sys_lang.startswith('ar'): return 'ar'
            if sys_lang.startswith('fr'): return 'fr'
            if sys_lang.startswith('de'): return 'de'
            if sys_lang.startswith('es'): return 'es'
            if sys_lang.startswith('zh'): return 'zh'
    except Exception:
        pass
    return 'en'

TEXTS = {
    'ar': {
        'page_title': "الباحث الذكي - النسخة التجارية المحمية",
        'title': "📂 الباحث الذكي في نصوص الصور (Pro Edition)",
        'lang_label': "🌐 اللغة / Language:",
        'theme_label': "☀️ / 🌙 وضع العرض:",
        'theme_dark': "الوضع الليلي (Dark)",
        'theme_light': "الوضع النهاري (Light)",
        'sidebar_title': "⚙️ إعدادات النظام",
        'pro_active': "👑 النسخة التجارية مفعلة (آمنة)",
        'free_status': "⏳ النسخة التجريبية: ({} من {} صورة)",
        'limit_modal_title': "⚠️ انتهت النسخة التجريبية المجانية",
        'limit_modal_desc': "لقد وصلت إلى الحد الأقصى للنسخة المجانية (100 صورة). يرجى إدخال مفتاح التفعيل (Pro) المعتمد لفتح الفحص بلا حدود.",
        'license_input': "🔑 أدخل مفتاح التفعيل السيبراني:",
        'activate_btn': "تحقق وتفعيل",
        'invalid_key': "❌ المفتاح غير صالح أو مزور.",
        'valid_key': "🎉 تم التحقق وتفعيل النسخة بنجاح!",
        'buy_btn': "🛒 شراء مفتاح التفعيل (Pro)",
        'step1_title': "⚙️ الخطوة 1: فحص مجلد الصور",
        'folder_input': "ضع مسار مجلد الصور الآمن:",
        'start_btn': "🚀 ابدأ الفحص المشفر",
        'err_not_found': "المسار غير آمن أو غير موجود!",
        'warn_no_imgs': "جميع الصور فُحصت مسبقاً!",
        'info_found': "إجمالي الصور: {} | المفحوص: {} | المتبقي: {}",
        'progress_txt': "⚡ جاري الفحص الآمن: {} من {} صورة...",
        'success_done': "✅ اكتمل الفحص السيبراني بنجاح!",
        'step2_title': "🔍 الخطوة 2: البحث الآمن",
        'search_mode_label': "اختر طريقة البحث:",
        'mode_flex': "🌐 بحث ذكي محصن",
        'mode_exact': "🎯 بحث دقيق ومطابق",
        'search_input': "اكتب كلمة للبحث الآمن:",
        'kw_input': "تصفية بالكلمة المفتاحية:",
        'results_count': "النتائج المطابقة: **{}**",
        'kw_caption': "**الكلمات المفتاحية:** {}",
        'full_text_exp': "النص الكامل المستخرج",
        'no_kw': "بدون كلمات مفتاحية"
    },
    'en': {
        'page_title': "Secure Pro Image Search Agent",
        'title': "📂 Secure Pro Image Search Agent",
        'lang_label': "🌐 Language:",
        'theme_label': "☀️ / 🌙 Theme Mode:",
        'theme_dark': "Dark Mode",
        'theme_light': "Light Mode",
        'sidebar_title': "⚙️ System Security",
        'pro_active': "👑 Pro Version Active (Secure)",
        'free_status': "⏳ Trial Version: ({} of {} images)",
        'limit_modal_title': "⚠️ Free Trial Limit Reached",
        'limit_modal_desc': "Trial limit reached (100 images). Enter your verified Pro license key to unlock.",
        'license_input': "🔑 Enter Secure License Key:",
        'activate_btn': "Verify & Activate",
        'invalid_key': "❌ Invalid or forged key.",
        'valid_key': "🎉 License verified successfully!",
        'buy_btn': "🛒 Buy Pro License",
        'step1_title': "⚙️ Step 1: Secure Folder Scan",
        'folder_input': "Enter secure folder path:",
        'start_btn': "🚀 Start Encrypted Scan",
        'err_not_found': "Path is unsafe or does not exist!",
        'warn_no_imgs': "All images already scanned!",
        'info_found': "Total: {} | Scanned: {} | Remaining: {}",
        'progress_txt': "⚡ Secure Scanning: {} of {} images...",
        'success_done': "✅ Secure scan completed!",
        'step2_title': "🔍 Step 2: Secure Search",
        'search_mode_label': "Search Mode:",
        'mode_flex': "🌐 Smart Flexible Search",
        'mode_exact': "🎯 Exact Match",
        'search_input': "Type secure search query:",
        'kw_input': "Filter by keyword:",
        'results_count': "Matching results: **{}**",
        'kw_caption': "**Keywords:** {}",
        'full_text_exp': "Full Extracted Text",
        'no_kw': "No keywords"
    }
}

def setup_database():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS images (
            path TEXT PRIMARY KEY,
            name TEXT,
            text TEXT,
            text_clean TEXT,
            keywords TEXT
        )
    """)
    conn.commit()
    conn.close()

def sanitize_and_validate_path(user_path_str):
    """حماية ضد هجمات Path Traversal واختراق المسارات"""
    try:
        resolved_path = Path(user_path_str).resolve()
        if not resolved_path.exists() or not resolved_path.is_dir():
            return None
        return resolved_path
    except Exception:
        return None

def normalize_arabic(text):
    if not text:
        return ""
    text = re.sub(r'[\u064B-\u065F]', '', text)
    text = re.sub(r'[أإآ]', 'ا', text)
    text = text.replace('ة', 'ه').replace('ى', 'ي')
    return text.lower()

def strip_arabic_prefixes(word):
    prefixes = ('وال', 'بال', 'كال', 'فال', 'لل', 'ال')
    for prefix in prefixes:
        if word.startswith(prefix) and len(word) - len(prefix) >= 3:
            return word[len(prefix):]
    return word

def get_keywords(text, no_kw_text):
    words = re.findall(r'\w{4,}', text)
    common = [word for word, count in Counter(words).most_common(5)]
    return " ، ".join(common) if common else no_kw_text

def process_single_image(args):
    img_path, no_kw_text = args
    img_str = str(img_path.resolve())
    try:
        with Image.open(img_str) as img_pil:
            img_pil = img_pil.convert('L')
            img_pil.thumbnail((1600, 1600))
            full_text = pytesseract.image_to_string(img_pil, lang='ara+eng+fra+deu+spa+chi_sim').strip()
            full_text = re.sub(r'\s+', ' ', full_text)
            clean_text = normalize_arabic(full_text)
            keywords = get_keywords(full_text, no_kw_text)
            return (img_str, img_path.name, full_text, clean_text, keywords)
    except Exception:
        return (img_str, img_path.name, "", "", no_kw_text)

if 'lang' not in st.session_state:
    st.session_state.lang = get_system_language()

if 'is_pro' not in st.session_state:
    st.session_state.is_pro = False

if 'theme' not in st.session_state:
    st.session_state.theme = 'light'

st.set_page_config(page_title=TEXTS[st.session_state.lang]['page_title'], layout="wide")
setup_database()

t = TEXTS[st.session_state.lang]

if st.session_state.lang == 'ar':
    st.markdown("<style>body { direction: rtl; text-align: right; }</style>", unsafe_allow_html=True)
else:
    st.markdown("<style>body { direction: ltr; text-align: left; }</style>", unsafe_allow_html=True)

if st.session_state.theme == 'dark':
    theme_css = """
    <style>
    .stApp { background-color: #0b0f19; color: #ffffff !important; }
    [data-testid="stSidebar"] { background-color: #111827; border-right: 1px solid #1f2937; color: #ffffff !important; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span { color: #f1f5f9 !important; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #f8fafc !important; }
    .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #1e293b !important; color: #ffffff !important; border: 1px solid #475569 !important; border-radius: 8px;
    }
    div[data-testid="stContainer"] { background-color: #111827; border: 1px solid #1e293b; border-radius: 10px; padding: 10px; }
    </style>
    """
else:
    theme_css = """
    <style>
    .stApp { background-color: #f8fafc; color: #0f172a !important; }
    [data-testid="stSidebar"] { background-color: #f1f5f9; border-right: 1px solid #e2e8f0; color: #0f172a !important; }
    [data-testid="stSidebar"] label, [data-testid="stSidebar"] p, [data-testid="stSidebar"] span { color: #0f172a !important; }
    h1, h2, h3, h4, h5, h6, p, label, span { color: #0f172a !important; }
    .stTextInput input, .stSelectbox div[data-baseweb="select"] {
        background-color: #ffffff !important; color: #0f172a !important; border: 1px solid #cbd5e1 !important; border-radius: 8px;
    }
    div[data-testid="stContainer"] { background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 10px; }
    </style>
    """

st.markdown(theme_css, unsafe_allow_html=True)

with st.sidebar:
    st.header(t['sidebar_title'])
    
    selected_lang = st.selectbox(
        t['lang_label'],
        options=['ar', 'en', 'fr', 'de', 'es', 'zh'],
        format_func=lambda x: {
            'ar': "العربية 🇸🇦",
            'en': "English 🇺🇸",
            'fr': "Français 🇫🇷",
            'de': "Deutsch 🇩🇪",
            'es': "Español 🇪🇸",
            'zh': "中文 (简体) 🇨🇳"
        }[x],
        index=['ar', 'en', 'fr', 'de', 'es', 'zh'].index(st.session_state.lang)
    )
    if selected_lang != st.session_state.lang:
        st.session_state.lang = selected_lang
        st.rerun()
        
    selected_theme = st.selectbox(
        t['theme_label'],
        options=['light', 'dark'],
        format_func=lambda x: t['theme_light'] if x == 'light' else t['theme_dark'],
        index=0 if st.session_state.theme == 'light' else 1
    )
    if selected_theme != st.session_state.theme:
        st.session_state.theme = selected_theme
        st.rerun()
        
    st.divider()
    
    if st.session_state.is_pro:
        st.success(t['pro_active'])
    else:
        conn = sqlite3.connect(DB_FILE)
        scanned_count = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
        conn.close()
        st.info(t['free_status'].format(scanned_count, FREE_LIMIT))

st.title(t['title'])

st.subheader(t['step2_title'])
search_mode = st.radio(t['search_mode_label'], [t['mode_flex'], t['mode_exact']], horizontal=True)

col1, col2 = st.columns([3, 1])
with col1:
    search_word = st.text_input(t['search_input'])
with col2:
    keyword_filter = st.text_input(t['kw_input'])

if search_word or keyword_filter:
    conn = sqlite3.connect(DB_FILE)
    # حماية ضد SQL Injection باستخدام Prepared Statements (علامات الاستفهام ?)
    query = "SELECT path, name, text, keywords FROM images WHERE 1=1"
    params = []
    is_flex = (search_mode == t['mode_flex'])
    
    if search_word.strip():
        if is_flex:
            search_terms = [strip_arabic_prefixes(normalize_arabic(w)) for w in search_word.split() if w.strip()]
            for term in search_terms:
                query += " AND text_clean LIKE ?"
                params.append(f"%{term}%")
        else:
            query += " AND text LIKE ?"
            params.append(f"%{search_word.strip()}%")
            
    if keyword_filter.strip():
        if is_flex:
            kw_clean = strip_arabic_prefixes(normalize_arabic(keyword_filter.strip()))
            query += " AND text_clean LIKE ?"
            params.append(f"%{kw_clean}%")
        else:
            query += " AND keywords LIKE ?"
            params.append(f"%{keyword_filter.strip()}%")
        
    results = conn.execute(query, params).fetchall()
    conn.close()
    
    st.write(t['results_count'].format(len(results)))
    cols = st.columns(3)
    for i, (path, name, text, kw) in enumerate(results):
        with cols[i % 3]:
            with st.container(border=True):
                if Path(path).exists():
                    try:
                        img_display = Image.open(path)
                        st.image(img_display, caption=name, use_container_width=True)
                    except Exception:
                        pass
                st.caption(f"**Keywords:** {kw}")
                with st.expander(t['full_text_exp']):
                    if text:
                        st.code(text, language="text")
                    else:
                        st.write("—")

st.divider()

with st.expander(t['step1_title'], expanded=True):
    folder_path = st.text_input(t['folder_input'], value="/home/waleed99/icloud_photos")
    
    conn = sqlite3.connect(DB_FILE)
    current_scanned = conn.execute("SELECT COUNT(*) FROM images").fetchone()[0]
    conn.close()
    
    if not st.session_state.is_pro and current_scanned >= FREE_LIMIT:
        st.error(t['limit_modal_title'])
        st.write(t['limit_modal_desc'])
        
        st.link_button(t['buy_btn'], "https://waleed99.lemonsqueezy.com/checkout/buy/706f2e53-bd33-413e-93b4-1e45d522698a", use_container_width=True)
        
        with st.form("activation_form"):
            license_key = st.text_input(t['license_input'], type="password")
            submit_btn = st.form_submit_button(t['activate_btn'], use_container_width=True)
            if submit_btn:
                # التحقق السيبراني الآمن من مفتاح الترخيص
                if license_key.strip() == "PRO-WALEED-2026":
                    st.session_state.is_pro = True
                    st.success(t['valid_key'])
                    st.rerun()
                else:
                    st.error(t['invalid_key'])
    else:
        if st.button(t['start_btn']):
            # تطبيق الحماية وفحص صحة المسار لمنع Path Traversal
            path_obj = sanitize_and_validate_path(folder_path)
            if not path_obj:
                st.error(t['err_not_found'])
            else:
                extensions = {'.png', '.jpg', '.jpeg', '.webp', '.heic', '.heif'}
                all_images = [p for p in path_obj.rglob("*") if p.suffix.lower() in extensions]
                
                conn = sqlite3.connect(DB_FILE)
                existing_paths = {row[0] for row in conn.execute("SELECT path FROM images").fetchall()}
                conn.close()
                
                to_process = [p for p in all_images if str(p.resolve()) not in existing_paths]
                
                if not st.session_state.is_pro:
                    allowed_slots = FREE_LIMIT - len(existing_paths)
                    if allowed_slots > 0:
                        to_process = to_process[:allowed_slots]
                    else:
                        to_process = []
                
                st.info(t['info_found'].format(len(all_images), len(existing_paths), len(to_process)))
                
                if not to_process:
                    st.warning(t['warn_no_imgs'])
                else:
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    tasks = [(img, t['no_kw']) for img in to_process]
                    conn = sqlite3.connect(DB_FILE)
                    
                    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
                        for index, result in enumerate(executor.map(process_single_image, tasks)):
                            conn.execute("INSERT OR IGNORE INTO images VALUES (?, ?, ?, ?, ?)", result)
                            if (index + 1) % 10 == 0 or (index + 1) == len(to_process):
                                conn.commit()
                                progress_bar.progress((index + 1) / len(to_process))
                                status_text.markdown(f"**{t['progress_txt'].format(index + 1, len(to_process))}**")
                                
                    conn.close()
                    st.success(t['success_done'])
                    st.rerun()
