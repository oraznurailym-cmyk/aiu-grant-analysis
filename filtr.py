import io
import re
from collections import Counter
import fitz
import pandas as pd
import streamlit as st

st.set_page_config(page_title='AIU | Грант талдауы', page_icon='🎓', layout='wide')
st.title('🎓 2026–2027 мемлекеттік гранттар талдауы')
st.caption('Астана халықаралық университеті — ОВПО коды: 185')

@st.cache_data(show_spinner=False)
def parse_pdf(data):
    rows = []
    doc = fitz.open(stream=data, filetype='pdf')
    program = ''
    section = ''
    pattern = re.compile(r'(?m)^\s*(\d{1,5})\s*\n\s*(00\d{7})\s*\n')
    for page_no, page in enumerate(doc, 1):
        text = page.get_text(sort=False)
        if 'СПИСОК ВУЗОВ' in text.upper() or 'ПЕРЕЧЕНЬ ВУЗОВ' in text.upper():
            continue
        # Әр беттегі білім беру бағдарламасының атауын анықтау
        for match in re.finditer(r'(?m)^\s*(B\d{3})\s*[-–]\s*([^\n]+)', text):
            program = match.group(1) + ' — ' + match.group(2).strip()
        for match in pattern.finditer(text):
            fragment = text[match.end():match.end()+260]
            # Келесі жазбаның басталуына дейін ғана тексереміз
            next_match = pattern.search(text, match.end())
            if next_match:
                fragment = text[match.end():next_match.start()]
            score_and_code = re.search(r'\n\s*(\d{1,3})\s*\n\s*(\d{3})\s*(?:\n|$)', fragment)
            if not score_and_code:
                continue
            name = fragment[:score_and_code.start()].strip().replace('\n', ' ')
            name = re.sub(r'\s+', ' ', name)
            if not name:
                continue
            rows.append({
                'ИКТ': match.group(2), 'Аты-жөні': name,
                'Балл': int(score_and_code.group(1)),
                'ОВПО': score_and_code.group(2),
                'Бағдарлама': program, 'PDF беті': page_no
            })
    doc.close()
    return pd.DataFrame(rows)

uploaded = st.file_uploader('PDF, Excel немесе CSV файлын таңдаңыз', type=['pdf', 'xlsx', 'csv'])
if uploaded is None:
    st.info('2026–2027 жылғы грант иелерінің PDF құжатын жүктеңіз.')
    st.stop()

with st.spinner('Барлық беттер талданып жатыр. Үлкен PDF бірнеше минут алуы мүмкін...'):
    data = uploaded.getvalue()
    if uploaded.name.lower().endswith('.pdf'):
        df = parse_pdf(data)
    elif uploaded.name.lower().endswith('.csv'):
        df = pd.read_csv(io.BytesIO(data), dtype={'ОВПО': str, 'ИКТ': str})
    else:
        df = pd.read_excel(io.BytesIO(data), dtype={'ОВПО': str, 'ИКТ': str})

if df.empty:
    st.error('Құжаттан студент жазбалары табылмады. PDF скан болса, OCR қажет.')
    st.stop()

if 'ОВПО' not in df.columns:
    st.error('ОВПО бағаны жоқ. Кестенің құрылымын тексеріңіз.')
    st.stop()

df['ОВПО'] = df['ОВПО'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).str.zfill(3)
df['ИКТ'] = df['ИКТ'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True).str.zfill(9)
df = df.drop_duplicates(subset=['ИКТ'])

st.sidebar.header('🔎 Сүзгілер')
uni = st.sidebar.selectbox('Университет коды', ['185'] + [x for x in sorted(df['ОВПО'].unique()) if x != '185'])
filtered = df[df['ОВПО'] == uni].copy()
if 'Бағдарлама' in filtered.columns:
    choices = sorted(filtered['Бағдарлама'].dropna().unique().tolist())
    programs = st.sidebar.multiselect('Мамандық', choices)
    if programs:
        filtered = filtered[filtered['Бағдарлама'].isin(programs)]
if 'Балл' in filtered.columns and not filtered.empty:
    low, high = int(filtered['Балл'].min()), int(filtered['Балл'].max())
    if low < high:
        a, b = st.sidebar.slider('Балл аралығы', low, high, (low, high))
        filtered = filtered[filtered['Балл'].between(a, b)]
query = st.sidebar.text_input('Аты-жөні немесе ИКТ бойынша іздеу')
if query:
    filtered = filtered[filtered.astype(str).apply(lambda s: s.str.contains(query, case=False, regex=False)).any(axis=1)]

c1, c2, c3 = st.columns(3)
c1.metric('Табылған студент', len(filtered))
c2.metric('Барлық өңделген жазба', len(df))
c3.metric('Қайталанбайтын ИКТ', df['ИКТ'].nunique())
st.subheader('Студенттер кестесі')
st.dataframe(filtered, width="stretch", hide_index=True)
if 'Бағдарлама' in filtered.columns and not filtered.empty:
    st.subheader('Мамандықтар бойынша бөлу')
    st.bar_chart(filtered['Бағдарлама'].value_counts())
st.download_button('📥 Нәтижені CSV жүктеу', filtered.to_csv(index=False).encode('utf-8-sig'), 'aiu_grants.csv', 'text/csv')
st.caption('Ескерту: PDF мәтінінен табылған жазбалар есептеледі. Құжаттағы скан беттер, бұзылған кестелер және жолға бөлінген күрделі жазбалар бөлек тексеруді қажет етеді.')

