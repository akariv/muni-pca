#!/usr/bin/env python
# coding: utf-8

# In[1]:


import dataflows as DF
import pandas as pd
import numpy as np
import requests
import re

DB = 'postgresql://readonly:readonly@db.datacity.org.il/datasets'

ENTITIES_URL = 'https://redash.hasadna.org.il/api/queries/1361/results.json?api_key=UDd9IGDUTqM8seDggkaCezRGO7kI440AINdrRkzS'
ENTITIES = requests.get(ENTITIES_URL).json()['query_result']['data']['rows']
ENTITIES = {x['symbol']: x['id'] for x in ENTITIES}

SUPPORTS_URL = 'https://redash.hasadna.org.il/api/queries/1362/results.json?api_key=Jv9V86TxVc9lbh5a2jVfTlTT25Z0o4kDnlfBX8DX'
SUPPORTS = requests.get(SUPPORTS_URL).json()['query_result']['data']['rows']

SUPPORT_PREFIXES = [
    ('045212', 'מורשת'),
    ('045213', 'התיישבות'),
    ('3308', 'התיישבות'),
    ('99', 'התיישבות'),
    ('045215', 'שוויון חברתי, חדשנות ודיגיטציה'),
    ('0457', 'שוויון חברתי, חדשנות ודיגיטציה'),
    ('83', 'שוויון חברתי, חדשנות ודיגיטציה'),
    ('0456', 'שיתוף פעולה'),
    ('0464', 'פיתוח הנגב והגליל'),
    ('0620', 'חרבות ברזל'),
    ('0622', 'תמיכה בשירותי דת'),
    ('22', 'תמיכה בשירותי דת'),
    ('18110101', 'מענקי איזון'),
    ('18110103', 'מענק הבירה'),
    ('18110301', 'מענקי איזון'),
    ('18110303', 'מענק הבירה'),
    ('18110344', 'מענק הבירה'),
    ('1811', 'מענקים ותמיכות אחרות'),
    ('1812', 'מענקי הקרן לצמצום פערים'),
    ('1940', 'מיזמי מדע'),
    ('1942', 'פעולות תרבות'),
    ('1943', 'תמיכה בספורט'),
    ('2060', 'חינוך בלתי פורמאלי והעשרה'),
    ('2067', 'חינוך בלתי פורמאלי והעשרה'),
    ('2061', 'חינוך מיוחד'),
    ('2062', 'גני ילדים'),
    ('2063', 'חינוך יסודי'),
    ('2064', 'חינוך תיכוני'),
    ('2069', 'חינוך ליהדות'),
    ('20', 'תמיכות במערכת החינוך'),
    ('23', 'תמיכות במערכת הרווחה'),
    ('24', 'תמיכות משרד הבריאות'),
    ('26', 'קידום איכות הסביבה'),
    ('30', 'קליטת עלייה'),
    ('3309', 'מנהלת תנופה'),
    ('33', 'חקלאות ובעלי חיים'),
    ('36', 'סבסוד מעונות יום ומשפחתונים'),
    ('37', 'פעולות תיירותיות'),
    ('38', 'תמיכה בעסקים'),
    ('40', 'תחבורה'),
    ('79', 'תחבורה'),
    ('54', 'תכנון'),
    ('60', 'תשתיות חינוך'),
    ('73', 'משק המים'),
]

MANY_WS = re.compile(r'\s+')
ENTITY_SUPPORTS = {}
for entity_id in ENTITIES.values():
    entity_supports = [x for x in SUPPORTS if x['entity_id'] == entity_id]

    buckets = {}
    usage = []
    for support in entity_supports:
        code = support['budget_code']
        for prefix, bucket in SUPPORT_PREFIXES:
            if code.startswith(prefix):
                rec = buckets.setdefault(bucket, dict(paid=0, approved=0))
                rec['paid'] += support['paid']
                rec['approved'] += support['approved']
                break
        if support['approved'] > 0 and prefix and 'מענק' not in prefix:
            if support['paid'] / support['approved'] > 1:
                usage.append(1)
            else:
                usage.append(support['paid'] / support['approved'])

    buckets = [dict(name=k, **v) for k, v in buckets.items()]
    # for b in buckets:
    #     b['usage'] = b['paid'] / b['approved'] if b['approved'] > 0 else 0
    supports = sorted(buckets, key=lambda x: x['paid'], reverse=True)[:10]

    buckets = {}
    for support in entity_supports:
        key = (support['supporting_ministry'], MANY_WS.sub(' ', support['support_title']))
        rec = buckets.setdefault(key, dict(paid=0, approved=0))
        rec['paid'] += support['paid']
        rec['approved'] += support['approved']
    buckets = [dict(ministry=k[0], title=k[1], **v) for k, v in buckets.items()]
    top = sorted(buckets, key=lambda x: x['paid'], reverse=True)[:10]
    usage = sum(usage) / len(usage) if usage else 0

    ENTITY_SUPPORTS[entity_id] = {
        'supports': supports,
        'top': top,
        'usage': usage,
    }

print(ENTITY_SUPPORTS['500287008'])

NAMES_QUERY = 'select distinct name from lamas_muni where year=2021'
all_city_names = DF.Flow(
    DF.load(DB, query=NAMES_QUERY, name='names'),
    DF.checkpoint('lamas_muni_names'),
).results()[0][0]
all_city_names = [x['name'] for x in all_city_names]
names = [x.replace("'", "''") for x in all_city_names]
names = ','.join(f"'{x}'" for x in names)

QUERY = f'select year, name, header, value from lamas_muni where name in ({names}) order by year'
print(QUERY)

DATA = DF.Flow(
    DF.load(DB, query=QUERY, name='lamas_muni'),
    DF.filter_rows(lambda row: row['value'] is not None),
    DF.filter_rows(lambda row: (row['value'] and row['value'] != '0' or
                                row['header'] not in ('הוצאות בתקציב הרגיל - סה"כ הוצאות בתקציב רגיל (אלפי ש"ח)', 'הכנסות בתקציב הרגיל - חיוב ארנונה סך הכל (שטח באלפי מ"ר)'))),
    DF.filter_rows(lambda row: row['year'] != 2021 or row['name'] not in (
        'בית שאן', 'נצרת', 'קריית שמונה', 'בוקעאתא', 'גן יבנה', 'חריש', 'משהד', 'קדימה-צורן', 'תל שבע'
    )),
    DF.join_with_self('lamas_muni', ['name', 'header'], dict(
        name=None,
        header=None,
        value=dict(name='value', aggregate='last')
    )),
    DF.checkpoint('lamas_muni'),
).results()[0][0]

entity_id_rows = []
for row in DATA:
    if row['header'] == 'כללי - סמל הרשות':
        entity_id = ENTITIES.get(row['value'])
        if entity_id:
            entity_id_rows.append({'name': row['name'], 'header': 'entity_id', 'value': entity_id})
DATA.extend(entity_id_rows)

voter_columns = ['מצביעים למפלגות חרדיות', 'מצביעי שמאל', 'מצביעי ימין', 'מצביעי מרכז', 'מצביעים למפלגות ערביות']
def normalize_voters(cols):
    def func(row):
        total = sum(row[col] or 0 for col in cols)
        for col in cols:
            row[col] = row[col] / total * 100
        return row
    return func

VOTERS = DF.Flow(
    DF.load('https://docs.google.com/spreadsheets/d/16FKQ51z5ijkqle4dXpCI-qyCtgNxG-8zp_moWN1QEGE/edit#gid=1595307595'),
    DF.set_type('מצביעי.+', type='number'),
    normalize_voters(voter_columns),
    DF.checkpoint('voting_stats')
).results()[0][0]
VOTERS_IDX = [x.pop('name') for x in VOTERS]

VOTERS = pd.DataFrame(VOTERS, index=VOTERS_IDX, columns=['מצביעים למפלגות חרדיות', 'מצביעי שמאל', 'מצביעי ימין', 'מצביעי מרכז', 'מצביעים למפלגות ערביות']).astype(np.float64)

SETT_TO_MUNI = DF.Flow(
    DF.load('https://docs.google.com/spreadsheets/d/16FKQ51z5ijkqle4dXpCI-qyCtgNxG-8zp_moWN1QEGE/edit#gid=594850932'),
    DF.select_fields(['שם_ישוב', 'שם_מועצה']),
    DF.set_type('שם_מועצה', transform=lambda v, row: v or row['שם_ישוב']),
    DF.rename_fields({
        'שם_ישוב': 'name',
        'שם_מועצה': 'muni'
    }),
    DF.checkpoint('settlement_to_muni')
).results()[0][0]
SETT_TO_MUNI = sorted(filter(lambda x: x['muni'] in all_city_names, SETT_TO_MUNI), key=lambda x: x['name'])


# In[ ]:


IGNORE_HEADERS = [
    'כללי - שנת קבלת מעמד מוניציפלי'
]

clean = []
for row in DATA:
    header = row['header']
    value = row['value']
    if header not in ('entity_id', ):
        try:
            value = float(value)
        except:
            try:
                value = int(value)
            except:
                name = None
                pass
    if value is not None:
        clean.append(dict(
            name=row['name'],
            header=row['header'],
            value=value
        ))


# In[2]:


from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer

# Convert to DataFrame
df = pd.DataFrame(clean)

# Pivot the data to get cities as rows and indicators as columns
pivoted_df = df.pivot(index='name', columns='header', values='value')
voter_columns = [ 'מצביעים למפלגות חרדיות', 'מצביעי שמאל', 'מצביעי ימין', 'מצביעי מרכז', 'מצביעים למפלגות ערביות']
for col in voter_columns:
    pivoted_df[col] = VOTERS[col]
pivoted_df['בריאות - שיעור מקרי סרטן ממוצע לשנה ל-100,000 תושבים'] = pivoted_df['בריאות - שיעור מקרי סרטן ממוצע לשנה ל-100,000 תושבים, גברים']  + pivoted_df['בריאות - שיעור מקרי סרטן ממוצע לשנה ל-100,000 תושבים, נשים']
pivoted_df['דמוגרפיה - דרוזים (אחוז)'] = pivoted_df['דמוגרפיה - דרוזים (אחוז)'].fillna(0)
pivoted_df['דמוגרפיה - יהודים (אחוז)'] = pivoted_df['דמוגרפיה - יהודים (אחוז)'].fillna(0)
pivoted_df['דמוגרפיה - מוסלמים (אחוז)'] = pivoted_df['דמוגרפיה - מוסלמים (אחוז)'].fillna(0)
pivoted_df['דמוגרפיה - נוצרים (אחוז)'] = pivoted_df['דמוגרפיה - נוצרים (אחוז)'].fillna(0)

POP = pivoted_df['דמוגרפיה - אוכלוסייה (סה"כ)'] / 1000
EXPENSE = pivoted_df['הוצאות בתקציב הרגיל - סה"כ הוצאות בתקציב רגיל (אלפי ש"ח)']
AREA = pivoted_df['שימושי קרקע - סך הכל שטח שיפוט (שטח בקמ"ר)'].replace({np.nan: None})
ARNONA_AREA = pivoted_df['הכנסות בתקציב הרגיל - חיוב ארנונה סך הכל (שטח באלפי מ"ר)']

configuration = [
    ('דירות שנבנו ב-2021', 'בנייה ודיור - גמר בנייה: מספר דירות (סה"כ)', 'POP', '1'),
    ('דירות למגורים', 'בנייה ודיור - מספר דירות למגורים לפי מרשם מבנים ודירות (סה"כ)', 'POP', '1'),
    ('מקרי סכרת לשנה', 'בריאות - שיעור מקרי סכרת ממוצע לשנה ל-1,000 תושבים', None, '1'),
    ('מקרי סרטן לשנה', 'בריאות - שיעור מקרי סרטן ממוצע לשנה ל-100,000 תושבים', None, '1'),
    ('פטירות לשנה', 'דמוגרפיה - פטירות (סה"כ)', 'POP', '1'),
    ('פטירת תינוקות', 'דמוגרפיה - שיעור פטירות תינוקות ל-1,000 לידות חי (אחוז)', None, '1'),
    ('לידות לשנה', 'דמוגרפיה - לידות חי (סה"כ)', 'POP', '1'),
    ('שיעור פריון', 'בריאות - שיעור פיריון כולל ל-1,000 תושבים', None),
    ('ריבוי אוכלוסיה', 'דמוגרפיה - ריבוי טבעי ל-1,000 תושבים (סה"כ)', None),
    ('טמפרטורה ממוצעת באוגוסט', "גיאוגרפיה - טמפ' ממוצעות באוגוסט (מעלות צלסיוס)", None),
    ('משקעים במ״מ', 'גיאוגרפיה - כמות משקעים ממוצעת במ"מ', None),
    ('מרחק מתל אביב', 'מדד פריפריאליות - ערך מדד', None),
    ('שטח', 'גיאוגרפיה - סך הכל שטח (קמ"ר)', None),
    ('מספר תושבים', 'דמוגרפיה - אוכלוסייה (סה"כ)', None),
    ('צעירים מתחת לגיל 17', 'דמוגרפיה - בני 0-17 (אחוז באוכלוסייה)', None, '1'),
    ('מבוגרים מעל גיל 65', 'דמוגרפיה - בני 65 ומעלה (אחוז באוכלוסייה)', None, '1'),
    ('קצב גידול האוכלוסיה', 'דמוגרפיה - גידול האוכלוסייה (אחוז)', None),
    ('דרוזים', 'דמוגרפיה - דרוזים (אחוז)', None, '1'),
    ('יהודים', 'דמוגרפיה - יהודים (אחוז)', None, '1'),
    ('מוסלמים', 'דמוגרפיה - מוסלמים (אחוז)', None, '1'),
    ('נוצרים', 'דמוגרפיה - נוצרים (אחוז)', None, '1'),
    ('נישאים', 'דמוגרפיה - נישאים (סה"כ)', 'POP', '1'),
    ('מתגרשים', 'דמוגרפיה - מתגרשים (סה"כ)', 'POP', '1'),
    ('עולים חדשים', 'דמוגרפיה - עולי 1990+ (אחוז)', None, '1'),
    ('צפיפות אוכלוסיה', 'דמוגרפיה - צפיפות אוכלוסייה לשטח בנוי למגורים (נפשות לקמ"ר)', None),
    ('מדד חברתי-כלכלי', 'מדד חברתי-כלכלי - ערך מדד', None),
    ('הוצאה לנפש על חינוך', 'הוצאות בתקציב הרגיל - חינוך (אלפי ש"ח)', 'POP', '1'),
    ('הוצאה לנפש על רווחה', 'הוצאות בתקציב הרגיל - רווחה (אלפי ש"ח)', 'POP', '1'),
    ('הוצאה לנפש על תרבות', 'הוצאות בתקציב הרגיל - תרבות (אלפי ש"ח)', 'POP', '1'),
    ('הכנסות ארנונה לא למגורים', 'הכנסות בתקציב הרגיל - ארנונה לא למגורים (גבייה) (אלפי ש"ח)', 'EXPENSE', '2'),
    ('הכנסות ארנונה למגורים', 'הכנסות בתקציב הרגיל - ארנונה למגורים (גבייה) (אלפי ש"ח)', 'EXPENSE', '2'),
    ('הכנסות מלוות איזון', 'הכנסות בתקציב הרגיל - מלוות לאיזון (אלפי ש"ח)', 'EXPENSE', '2'),
    ('השתתפות משרדי הממשלה', 'הכנסות בתקציב הרגיל - הכנסות מהממשלה (אלפי ש"ח)', 'EXPENSE', '2'),
    ('גירעון', 'נתוני תקציב - עודף/גירעון - גירעון שנתי בתקציב הרגיל (אלפי ש"ח)', 'EXPENSE', '2'),
    ('אחוז גביית ארנונה', 'הכנסות בתקציב הרגיל - ארנונה למגורים (יחס גבייה ב-% לכלל החיובים)', None),
    ('שטח מגורים', 'הכנסות בתקציב הרגיל - חיוב ארנונה למגורים (שטח באלפי מ"ר)', 'ARNONA_AREA', '3'),
    ('שטח חקלאי', 'הכנסות בתקציב הרגיל - חיוב ארנונה לאדמה חקלאית (שטח באלפי מ"ר)', 'ARNONA_AREA', '3'),
    ('שטח עסקים', 'הכנסות בתקציב הרגיל - חיוב ארנונה לעסקים (שטח באלפי מ"ר)', 'ARNONA_AREA', '3'),
    ('זכאים לבגרות', 'חינוך והשכלה - זכאים לתעודת בגרות מבין תלמידי כיתות יב (אחוז)', None),
    ('ממוצע תלמידים לכיתה', 'חינוך והשכלה - ממוצע תלמידים לכיתה (סה"כ)', None),
    ('סטודנטים', 'חינוך והשכלה - סטודנטים מתוך אוכלוסיית בני 20-25 (אחוז)', None, '1'),
    ('תלמידים למורה', 'חינוך והשכלה - עובדי הוראה - ממוצע תלמידים למורה', None),
    ('תלמידים נושרים', 'חינוך והשכלה - תלמידים נושרים (אחוז)', None),
    ('מורשעים', 'פשיעה ומשפט - מבוגרים תושבי ישראל המורשעים בדין, שיעור ל-1,000 בני 19 ומעלה', None, '1'),
    ('פארקים', 'שימושי קרקע - גינון לנוי פארק ציבורי (שטח בקמ"ר)', 'AREA', '3'),
    ('מקבלי דמי אבטלה', 'שכר ורווחה - אחוז מקבלי דמי אבטלה מבני 67-20 (שנתי)', None, '1'),
    ('מקבלי הבטחת הכנסה', 'שכר ורווחה - מקבלי הבטחת הכנסה (נפשות)', 'POP', '1'),
    ('מרוויחי שכר מינימום', 'שכר ורווחה - שכירים המשתכרים עד שכר מינימום (אחוז)', None, '1'),
    ('אי שויון כלכלי', "שכר ורווחה - מדד אי-השוויון - שכירים (מדד ג'יני, 0 שוויון מלא)", None),
    ('ילדים במשפחות עם 5+ ילדים', 'שכר ורווחה - מספר הילדים מקבלי קצבאות בגין ילדים במשפחות עם 5 ילדים ומעלה', 'POP', '1'),
    ('שכירים', 'שכר ורווחה - מספר השכירים (סה"כ)', 'POP', '1'),
    ('עצמאים', 'שכר ורווחה - מספר העצמאים (סה"כ)', 'POP', '1'),
    ('שכר ממוצע', 'שכר ורווחה - שכר חודשי ממוצע של שכירים (ש"ח)', None),
    ('מצביעים למפלגות חרדיות', 'מצביעים למפלגות חרדיות', None, '1'),
    ('מצביעי שמאל', 'מצביעי שמאל', 'POP', '1'),
    ('מצביעי ימין', 'מצביעי ימין', 'POP', '1'),
    ('מצביעי מרכז', 'מצביעי מרכז', 'POP', '1'),
    ('מצביעים למפלגות ערביות', 'מצביעים למפלגות ערביות', 'POP', '1'),
]

new_df = pd.DataFrame(index=pivoted_df.index)
for col, source, norm, *annotations in configuration:
    new_df[col] = pivoted_df[source]
    if norm == 'POP':
        new_df[col] = new_df[col] / POP
    elif norm == 'EXPENSE':
        new_df[col] = new_df[col] / EXPENSE
    elif norm == 'ARNONA_AREA':
        new_df[col] = new_df[col] / ARNONA_AREA
    elif norm == 'AREA':
        new_df[col] = new_df[col] / AREA

new_df['מועצה אזורית'] = (pivoted_df['כללי - מעמד מוניציפלי'] == 'מועצה אזורית')*1

DISSIMILARITY_COLUMNS = [
    'דירות שנבנו ב-2021', 'דירות למגורים', 'מקרי סכרת לשנה', 'מקרי סרטן לשנה',
       'פטירות לשנה', 'פטירת תינוקות', 'לידות לשנה', 'שיעור פריון',
       'ריבוי אוכלוסיה', 
        'צעירים מתחת לגיל 17',
       'מבוגרים מעל גיל 65', 'דרוזים', 'יהודים',
       'מוסלמים', 'נוצרים', 'נישאים', 'מתגרשים', 'עולים חדשים',
       'צפיפות אוכלוסיה', 'מדד חברתי-כלכלי', 'הוצאה לנפש על חינוך',
       'הוצאה לנפש על רווחה', 'הוצאה לנפש על תרבות',
       'הכנסות ארנונה לא למגורים', 'הכנסות ארנונה למגורים',
       'הכנסות מלוות איזון', 'השתתפות משרדי הממשלה', 'שטח חקלאי',
       'שטח עסקים', 'זכאים לבגרות', 'ממוצע תלמידים לכיתה', 'סטודנטים',
       'תלמידים למורה', 'תלמידים נושרים', 'פארקים',
       'מקבלי דמי אבטלה', 'מקבלי הבטחת הכנסה', 'מרוויחי שכר מינימום',
       'אי שויון כלכלי', 'ילדים במשפחות עם 5+ ילדים', 'שכירים', 'עצמאים',
       'שכר ממוצע', *voter_columns
]

# Find which indexes in new_df don't exist in VOTERS:
indexes = [x for x in new_df.index if x not in VOTERS.index.values]
print(indexes)


# In[ ]:


# Handle missing values
imputer = SimpleImputer(missing_values=np.nan, strategy='mean')
data_imputed = imputer.fit_transform(new_df)

# Standardize the features
scaler = StandardScaler()
data_scaled = scaler.fit_transform(data_imputed)
pivoted_df_scaled = pd.DataFrame(data_scaled, columns=new_df.columns, index=new_df.index)
print(pivoted_df_scaled['מועצה אזורית'])

# Apply PCA
n_components = 3
pca = PCA(n_components='mle')#n_components)  # for example, reduce to 2 dimensions
principal_components = pca.fit_transform(data_scaled)
n_components = len(pca.components_)


# In[ ]:


# Explained variance ratio
explained_variance_ratio = pca.explained_variance_ratio_

# Print the explained variance ratio for each principal component
for i, variance in enumerate(explained_variance_ratio):
    print(f"Principal Component {i+1}: {variance:.2f}")
    


# In[ ]:


print_ = []
count = 7
for i in range(count):
    print_.append([])

# Sort by the absolute value of the weights
for i in range(n_components):
    # Match each weight with its corresponding feature
    component = pca.components_[i]
    feature_weights = zip(new_df.columns, component)
    sorted_features = sorted(feature_weights, key=lambda x: np.abs(x[1]), reverse=True)[:count]
    for j, (feature, weight) in enumerate(sorted_features):
        print_[j].append(f"{feature:30s}: {weight:5.2f}")

for i in range(count):
    print('\t\t'.join(print_[i]))


# In[ ]:


FILES = {
    'configuration': dict(
        columns=dict(
            (x[0], dict(norm=x[2], annotations=x[3:])) for x in configuration
        )
    ),
    'settlements': SETT_TO_MUNI,
    'cities': dict(
        (city_name, dict(
            norm=dict(
                POP=POP.loc[city_name],
                EXPENSE=EXPENSE.loc[city_name],
                ARNONA_AREA=ARNONA_AREA.loc[city_name],
                AREA=AREA.loc[city_name]
            ),
            values=dict(
                (col, pivoted_df.loc[city_name][orig_col])
                for col, orig_col, *_ in configuration
                if not np.isnan(pivoted_df.loc[city_name][orig_col])
            ),
            orig=dict(
                (col, pivoted_df.loc[city_name][col])
                for col in pivoted_df.columns
                if (not np.isreal(pivoted_df.loc[city_name][col]) or not np.isnan(pivoted_df.loc[city_name][col]))
            ),
            supports=ENTITY_SUPPORTS.get(pivoted_df.loc[city_name]['entity_id'])
        )) for city_name in all_city_names
    ),
    'distances': dict()
}


# In[ ]:


from sklearn.metrics import pairwise_distances
import json

# Create a DataFrame with the principal components
principal_df = pd.DataFrame(data = principal_components, 
                            columns = [f'x{i}' for i in range(n_components)],
                            index = pivoted_df.index)

distances = pairwise_distances(principal_df, metric='euclidean')

# Find the indices of the 5 nearest neighbors for each row
nearest_neighbors = np.argsort(distances, axis=1)[:, 1:]  # Exclude the first one as it will be the row itself

# Create a dictionary or DataFrame to store the nearest neighbors
nearest_dict = {}
for idx, neighbors in enumerate(nearest_neighbors):
    nearest_dict[principal_df.index[idx]] = principal_df.index[neighbors].tolist()

def config_for_column(col):
    for conf in configuration:
        if conf[0] == col:
            return conf[1], conf[2]
    return None

for city_name in all_city_names:
    print(f'{city_name}:')

    original_city = new_df.loc[city_name]
    nearest_cities = nearest_dict[city_name]
    muni_status = new_df.loc[city_name]['מועצה אזורית']
    for nearest_city in nearest_cities:

        print(f'\t{nearest_city}:')
        original_nearest_city = new_df.loc[nearest_city]
        if muni_status != original_nearest_city['מועצה אזורית']:
            continue

        row1 = pivoted_df_scaled.loc[city_name, DISSIMILARITY_COLUMNS]
        row2 = pivoted_df_scaled.loc[nearest_city, DISSIMILARITY_COLUMNS]
        differences = np.abs(row1 - row2)
        sorted_diffs = differences.sort_values(ascending=False)
        most_different_columns = sorted_diffs.index.tolist()
        most_different_columns_actual = []
        for different_column in most_different_columns:
            if differences[different_column] < 1.25 and len(most_different_columns_actual) > 1:
                break
            original_val = original_city[different_column]
            original_nearest_val = original_nearest_city[different_column]
            if not np.isnan(original_val) and not np.isnan(original_nearest_val):
                most_different_columns_actual.append(different_column)
            if len(most_different_columns_actual) == 5:
                break
        FILES['distances'].setdefault(city_name, []).append([nearest_city, most_different_columns_actual])
        if len(FILES['distances'].get(city_name)) == 10:
            break

for k, v in FILES.items():
    with open(f'../src/assets/{k}.json', 'w') as json_output:
        json.dump(v, json_output, ensure_ascii=False, sort_keys=True)


# In[ ]:


# from sklearn.manifold import TSNE
# import matplotlib.pyplot as plt
# from sklearn.preprocessing import MinMaxScaler

# # Extract the color values from the original DataFrame
# color_values = new_df['אחוז גביית ארנונה'].values

# scaler = MinMaxScaler()
# color_values_scaled = scaler.fit_transform(color_values.reshape(-1, 1)).flatten()

# # Apply t-SNE
# tsne = TSNE(n_components=2, random_state=42)  # You can adjust the parameters as needed
# tsne_results = tsne.fit_transform(principal_components)

# # Create a scatter plot of the t-SNE output
# plt.figure(figsize=(6, 6))  # 6x6 inches plot
# plt.scatter(principal_components[:, 0], principal_components[:, 1], c=color_values_scaled, cmap='viridis')
# # plt.scatter(tsne_results[:, 0], tsne_results[:, 1], c=color_values_scaled, cmap='viridis')

# # # Optionally add labels, titles, etc.
# # plt.title("t-SNE of PCA Results")
# # plt.xlabel("t-SNE Feature 1")
# # plt.ylabel("t-SNE Feature 2")

# # Save the plot as a 600x600 PNG image
# plt.savefig("tsne_output.png", dpi=100)  # 100 dpi results in a 600x600 image
# plt.close()

