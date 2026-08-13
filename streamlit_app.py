# %%writefile chat_coach_app.py
import streamlit as st
import pandas as pd
import numpy as np
import json
import re
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize
from nltk.sentiment import SentimentIntensityAnalyzer
from collections import Counter, defaultdict
import gc
import hashlib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.cluster import KMeans
import warnings
warnings.filterwarnings('ignore')

# ============ ROBUST NLTK SETUP ============
@st.cache_resource
def setup_nltk():
    """Download and setup NLTK data with fallbacks."""
    for resource in ['punkt', 'stopwords', 'vader_lexicon', 'punkt_tab']:
        try:
            nltk.data.find(f'tokenizers/{resource}' if resource == 'punkt' else
                          f'corpora/{resource}' if resource == 'stopwords' else
                          f'sentiment/{resource}' if resource == 'vader_lexicon' else
                          f'tokenizers/{resource}')
        except LookupError:
            try:
                nltk.download(resource, quiet=True)
            except:
                pass

setup_nltk()

# Initialize session state
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'file_uploaded' not in st.session_state:
    st.session_state.file_uploaded = False
if 'current_archetype' not in st.session_state:
    st.session_state.current_archetype = None

st.set_page_config(
    page_title="AI Chat Coach - Your Personal AI Usage Analyst",
    page_icon="🧠",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        color: #6C63FF;
        text-align: center;
        margin-bottom: 0.5rem;
    }
    .sub-header {
        font-size: 1.5rem;
        color: #6C63FF;
        border-bottom: 2px solid #6C63FF;
        padding-bottom: 0.2rem;
        margin-top: 2rem;
    }
    .archetype-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 1rem;
        color: white;
        text-align: center;
        margin: 1rem 0;
    }
    .archetype-name {
        font-size: 2.5rem;
        font-weight: bold;
    }
    .archetype-desc {
        font-size: 1.1rem;
        opacity: 0.9;
        margin-top: 0.5rem;
    }
    .stat-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 0.5rem;
        text-align: center;
        border: 1px solid #dee2e6;
    }
    .stat-value {
        font-size: 2rem;
        font-weight: bold;
        color: #6C63FF;
    }
    .stat-label {
        font-size: 0.9rem;
        color: #6c757d;
    }
    .insight-box {
        background-color: #e8f4fd;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #6C63FF;
        margin: 0.5rem 0;
    }
    .message-card {
        background-color: #f8f9fa;
        border: 1px solid #dee2e6;
        border-radius: 0.5rem;
        padding: 1rem;
        margin: 0.5rem 0;
    }
    .message-card.user {
        border-left: 4px solid #6C63FF;
    }
    .message-card.ai {
        border-left: 4px solid #28a745;
    }
</style>
""", unsafe_allow_html=True)

# ============ JSON PARSER ============
def parse_chat_json(json_data):
    """Parse nested JSON structure with mapping and fragments."""
    records = []
    
    if isinstance(json_data, str):
        try:
            json_data = json.loads(json_data)
        except json.JSONDecodeError:
            return None
    
    if isinstance(json_data, list):
        for conversation in json_data:
            records.extend(extract_from_conversation(conversation))
    elif isinstance(json_data, dict):
        records.extend(extract_from_conversation(json_data))
    
    return pd.DataFrame(records) if records else None

def extract_from_conversation(conv):
    """Extract messages from a conversation object."""
    records = []
    conv_id = conv.get('id', '')
    conv_title = conv.get('title', '')
    
    mapping = conv.get('mapping', {})
    for node_id, node_data in mapping.items():
        if node_data and 'message' in node_data:
            message_data = node_data['message']
            if message_data:
                record = extract_message_from_node(message_data, conv_id, conv_title)
                if record:
                    records.append(record)
    return records

def extract_message_from_node(message_data, conv_id, conv_title):
    """Extract message content from a node."""
    if not message_data:
        return None
    record = {
        'conversation_id': conv_id,
        'conversation_title': conv_title,
        'model': message_data.get('model', ''),
        'inserted_at': message_data.get('inserted_at', ''),
    }
    fragments = message_data.get('fragments', [])
    message_text = ''
    for fragment in fragments:
        if fragment.get('type') in ('RESPONSE', 'REQUEST'):
            message_text += fragment.get('content', '')
    record['message'] = message_text
    record['message_length'] = len(message_text)
    return record

def build_conversation_flow(df):
    """Build conversation flow by identifying user/AI turns."""
    if df.empty:
        return df
    
    if 'inserted_at' in df.columns:
        df['inserted_at'] = pd.to_datetime(df['inserted_at'], errors='coerce')
        df = df.sort_values('inserted_at').reset_index(drop=True)
    
    request_patterns = ['help me', 'write me', 'please', 'can you', 'could you', 'i need',
                        'what is', 'how do', 'explain', 'list', 'tell me']
    
    for idx, row in df.iterrows():
        msg = str(row.get('message', '')).lower()
        if any(pattern in msg for pattern in request_patterns):
            df.loc[idx, 'sender_type'] = 'user'
        elif msg and len(msg) > 50:
            df.loc[idx, 'sender_type'] = 'ai'
        else:
            df.loc[idx, 'sender_type'] = 'unknown'
    
    if not df.empty:
        first_user_idx = df[df['sender_type'] == 'user'].index
        if len(first_user_idx) > 0:
            current_type = 'user'
            for i in range(len(df)):
                if pd.isna(df.loc[i, 'sender_type']):
                    df.loc[i, 'sender_type'] = current_type
                    current_type = 'ai' if current_type == 'user' else 'user'
    
    df['user'] = df['sender_type'].apply(lambda x: 'User' if x == 'user' else 'AI')
    df['ai_interface'] = df['model'].apply(lambda x: x.split('-')[0] if x else 'DeepSeek')
    return df

# ============ SAFE TOKENIZATION ============
def safe_word_tokenize(text):
    try:
        return word_tokenize(text)
    except:
        return text.split()

def safe_sent_tokenize(text):
    try:
        return sent_tokenize(text)
    except:
        return text.split('.')

# ============ DATA PROCESSING ============
@st.cache_data
def preprocess_text(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'http\S+', '', text)
    text = re.sub(r'[^a-zA-Z\s]', '', text)
    return text

@st.cache_data
def analyze_sentiment_batch(texts):
    try:
        sia = SentimentIntensityAnalyzer()
        return [sia.polarity_scores(t)['compound'] if isinstance(t, str) and t.strip() else 0 for t in texts]
    except:
        return [0] * len(texts)

@st.cache_data
def extract_topics(texts, n_topics=5, n_words=8):
    """Extract topics using LDA."""
    valid_texts = [t for t in texts if isinstance(t, str) and len(t.strip()) > 10]
    if len(valid_texts) < 5:
        return []
    
    if len(valid_texts) > 500:
        valid_texts = valid_texts[:500]
    
    processed = [preprocess_text(t) for t in valid_texts]
    processed = [t for t in processed if len(t) > 5]
    if len(processed) < 3:
        return []
    
    try:
        vectorizer = TfidfVectorizer(max_features=200, stop_words='english')
        tfidf = vectorizer.fit_transform(processed)
        
        n_topics = min(n_topics, max(1, len(processed) // 3))
        lda = LatentDirichletAllocation(n_components=n_topics, random_state=42)
        lda.fit(tfidf)
        
        feature_names = vectorizer.get_feature_names_out()
        topics = []
        for topic_idx, topic in enumerate(lda.components_):
            top_words = [feature_names[i] for i in topic.argsort()[-n_words:][::-1]]
            topics.append({
                'topic': topic_idx + 1,
                'words': top_words,
                'weight': topic.sum() / lda.components_.sum()
            })
        return topics
    except:
        return []

@st.cache_data
def extract_keywords(texts, top_n=15):
    try:
        stop_words = set(stopwords.words('english'))
    except:
        stop_words = set()
    all_words = []
    sample_texts = texts[:500] if len(texts) > 500 else texts
    for text in sample_texts:
        if isinstance(text, str) and text.strip():
            words = safe_word_tokenize(preprocess_text(text))
            all_words.extend([w for w in words if w not in stop_words and len(w) > 2])
    return Counter(all_words).most_common(top_n)

@st.cache_data
def extract_question_types(texts):
    """Extract question types from messages with examples."""
    question_patterns = {
        'how': r'\bhow\b', 'what': r'\bwhat\b', 'why': r'\bwhy\b',
        'when': r'\bwhen\b', 'where': r'\bwhere\b', 'who': r'\bwho\b',
        'which': r'\bwhich\b', 'can': r'\bcan\b', 'could': r'\bcould\b',
        'would': r'\bwould\b', 'will': r'\bwill\b', 'is': r'\bis\b',
        'are': r'\bare\b', 'do': r'\bdo\b', 'does': r'\bdoes\b'
    }
    
    question_counts = {k: {'count': 0, 'examples': []} for k in question_patterns}
    total_questions = 0
    
    for text in texts:
        if isinstance(text, str):
            text_lower = text.lower()
            for q_type, pattern in question_patterns.items():
                if re.search(pattern, text_lower):
                    question_counts[q_type]['count'] += 1
                    total_questions += 1
                    # Store example (truncated)
                    if len(question_counts[q_type]['examples']) < 3:
                        example = text[:200] + ('...' if len(text) > 200 else '')
                        question_counts[q_type]['examples'].append(example)
                    break
    
    return question_counts, total_questions

@st.cache_data
def get_longest_context_messages(df, n=5):
    """Get the top N longest user messages and their corresponding AI responses."""
    # Group by conversation
    conversations = df.groupby('conversation_id')
    
    long_exchanges = []
    for conv_id, conv_df in conversations:
        conv_df = conv_df.sort_values('inserted_at')
        user_msgs = conv_df[conv_df['sender_type'] == 'user'].copy()
        ai_msgs = conv_df[conv_df['sender_type'] == 'ai'].copy()
        
        for idx, user_row in user_msgs.iterrows():
            msg_length = len(str(user_row['message']))
            # Find the next AI response after this user message
            user_time = user_row['inserted_at']
            ai_responses = ai_msgs[ai_msgs['inserted_at'] > user_time].head(1)
            
            if not ai_responses.empty:
                ai_response = ai_responses.iloc[0]
                combined_length = msg_length + len(str(ai_response['message']))
                long_exchanges.append({
                    'conversation_title': conv_df.iloc[0]['conversation_title'],
                    'conversation_id': conv_id,
                    'user_message': user_row['message'],
                    'user_message_length': msg_length,
                    'ai_response': ai_response['message'],
                    'ai_response_length': len(str(ai_response['message'])),
                    'combined_length': combined_length,
                    'timestamp': user_time
                })
    
    # Sort by combined length and return top N
    long_exchanges.sort(key=lambda x: x['combined_length'], reverse=True)
    return long_exchanges[:n]

@st.cache_data
def get_representative_conversations(df, n_longest=5, n_shortest=5):
    """Get the longest and shortest conversations by total message count and length."""
    conversations = df.groupby('conversation_id')
    
    conv_stats = []
    for conv_id, conv_df in conversations:
        total_chars = conv_df['message'].astype(str).str.len().sum()
        msg_count = len(conv_df)
        title = conv_df.iloc[0]['conversation_title']
        
        # Get a summary of the conversation content
        user_messages = conv_df[conv_df['sender_type'] == 'user']['message'].tolist()
        ai_messages = conv_df[conv_df['sender_type'] == 'ai']['message'].tolist()
        
        conv_stats.append({
            'conversation_id': conv_id,
            'title': title,
            'total_chars': total_chars,
            'msg_count': msg_count,
            'user_messages': user_messages,
            'ai_messages': ai_messages,
            'keywords': extract_keywords(user_messages + ai_messages, 5)
        })
    
    conv_stats.sort(key=lambda x: x['total_chars'], reverse=True)
    longest = conv_stats[:n_longest]
    shortest = conv_stats[-n_shortest:] if len(conv_stats) >= n_shortest else conv_stats
    
    return longest, shortest

@st.cache_data
def generate_themes_summary(question_counts, keywords, longest_convs):
    """Generate themes summary using question types, keywords, and conversation analysis."""
    themes = []
    
    # Analyze dominant question patterns
    sorted_questions = sorted(question_counts.items(), key=lambda x: x[1]['count'], reverse=True)
    dominant_q_types = [q[0] for q in sorted_questions[:5] if q[1]['count'] > 0]
    
    if 'how' in dominant_q_types and 'what' in dominant_q_types:
        themes.append({
            'theme': 'Practical Problem-Solving & Knowledge Seeking',
            'description': 'You frequently ask "how" and "what" questions, indicating a strong drive to understand concepts and apply them practically.',
            'confidence': 'High'
        })
    
    if 'why' in dominant_q_types:
        themes.append({
            'theme': 'Deep Analytical Thinking',
            'description': 'Your "why" questions suggest you seek to understand underlying causes and fundamental principles.',
            'confidence': 'Medium'
        })
    
    if 'can' in dominant_q_types or 'could' in dominant_q_types or 'would' in dominant_q_types:
        themes.append({
            'theme': 'Exploration of Possibilities',
            'description': 'You explore what\'s possible with AI, testing boundaries and considering hypothetical scenarios.',
            'confidence': 'High' if 'can' in dominant_q_types else 'Medium'
        })
    
    # Analyze keywords for thematic clusters
    if keywords:
        tech_keywords = {'code', 'function', 'data', 'python', 'api', 'programming', 'software', 'development'}
        creative_keywords = {'write', 'story', 'create', 'design', 'idea', 'creative', 'art', 'music'}
        business_keywords = {'business', 'marketing', 'strategy', 'project', 'management', 'team', 'startup'}
        
        kw_set = set([k[0].lower() for k in keywords[:20]])
        
        if kw_set & tech_keywords:
            themes.append({
                'theme': 'Technology & Development Focus',
                'description': 'Your vocabulary suggests strong engagement with technical topics, software development, or data-related work.',
                'confidence': 'High' if len(kw_set & tech_keywords) > 3 else 'Medium'
            })
        
        if kw_set & creative_keywords:
            themes.append({
                'theme': 'Creative & Content Creation',
                'description': 'You use AI as a creative partner, exploring writing, design, or other creative endeavors.',
                'confidence': 'Medium'
            })
        
        if kw_set & business_keywords:
            themes.append({
                'theme': 'Business & Strategy',
                'description': 'Your conversations show a focus on business planning, strategy, or professional development.',
                'confidence': 'Medium'
            })
    
    # Analyze longest conversations for deeper themes
    if longest_convs:
        all_kw = []
        for conv in longest_convs:
            all_kw.extend([k[0] for k in conv['keywords']])
        
        if all_kw:
            top_long_kw = Counter(all_kw).most_common(3)
            themes.append({
                'theme': f'Deep Dive Areas: {", ".join([k[0] for k in top_long_kw])}',
                'description': 'Your most extensive conversations revolve around these topics, suggesting areas of deep interest or complex problem-solving.',
                'confidence': 'High'
            })
    
    # Ensure we have at least some themes
    if not themes:
        themes.append({
            'theme': 'Diverse AI Usage',
            'description': 'Your conversations span various topics, showing a balanced and exploratory approach to AI interaction.',
            'confidence': 'Medium'
        })
    
    return themes

@st.cache_data
def generate_conversation_summary(conversation):
    """Generate a brief summary of what a conversation was about."""
    user_msgs = ' '.join(conversation['user_messages'][:3])
    ai_msgs = ' '.join(conversation['ai_messages'][:3])
    
    # Extract key terms
    keywords = conversation['keywords']
    kw_str = ', '.join([k[0] for k in keywords[:3]])
    
    # Simple summary based on keywords and message patterns
    summary = f"This conversation covers {kw_str}. "
    
    if len(conversation['user_messages']) > 5:
        summary += f"With {len(conversation['user_messages'])} user messages, this was a detailed exchange. "
    else:
        summary += f"It was a focused discussion with {len(conversation['user_messages'])} exchanges. "
    
    # Add context about question types
    if any('how' in msg.lower() for msg in conversation['user_messages']):
        summary += "You asked how-to questions, seeking practical guidance."
    elif any('why' in msg.lower() for msg in conversation['user_messages']):
        summary += "You explored underlying reasons and deeper understanding."
    elif any('?' in msg for msg in conversation['user_messages']):
        summary += "Your questions showed curiosity and engagement."
    
    return summary

@st.cache_data
def identify_projects(texts):
    """Identify potential projects from conversations."""
    project_indicators = [
        'project', 'build', 'create', 'develop', 'start', 'launch',
        'plan', 'design', 'implement', 'setup', 'configure', 'campaign',
        'initiative', 'movement', 'organize', 'coordinate', 'lead', 'manage'
    ]
    project_keywords = []
    for text in texts[:200]:
        if isinstance(text, str):
            text_lower = text.lower()
            for indicator in project_indicators:
                if indicator in text_lower:
                    words = text_lower.split()
                    for i, word in enumerate(words):
                        if word == indicator and i < len(words) - 1:
                            project_keywords.append(words[i+1])
    return Counter(project_keywords).most_common(10)

@st.cache_data
def calculate_growth_metrics(df):
    """Calculate growth metrics over time."""
    if 'inserted_at' not in df.columns or len(df) < 5:
        return {}
    df['inserted_at'] = pd.to_datetime(df['inserted_at'], errors='coerce')
    df['date'] = df['inserted_at'].dt.date
    daily_counts = df.groupby('date').size().reset_index(name='count')
    growth_rate = ((daily_counts['count'].iloc[-1] - daily_counts['count'].iloc[0]) / 
                   max(daily_counts['count'].iloc[0], 1)) * 100 if len(daily_counts) > 1 else 0
    
    sentiment_change = 0
    if 'sentiment_score' in df.columns:
        df['sentiment_score'] = pd.to_numeric(df['sentiment_score'], errors='coerce')
        sentiment_trend = df.groupby('date')['sentiment_score'].mean().reset_index()
        if len(sentiment_trend) > 1:
            sentiment_change = sentiment_trend['sentiment_score'].iloc[-1] - sentiment_trend['sentiment_score'].iloc[0]
    
    question_growth = 0
    if 'message' in df.columns:
        daily_questions = df.groupby('date')['message'].apply(
            lambda x: sum(1 for msg in x if isinstance(msg, str) and '?' in msg)
        ).reset_index(name='questions')
        if len(daily_questions) > 1:
            question_growth = ((daily_questions['questions'].iloc[-1] - daily_questions['questions'].iloc[0]) / 
                              max(daily_questions['questions'].iloc[0], 1)) * 100
    
    total_days = (df['inserted_at'].max() - df['inserted_at'].min()).days
    return {'growth_rate': growth_rate, 'sentiment_change': sentiment_change,
            'question_growth': question_growth, 'total_days': total_days}

# ============ COGNITIVE PROFILE GENERATOR ============
def generate_cognitive_profile(question_counts, stats):
    """Generate a paragraph describing how the user thinks based on question type distribution."""
    total_q = sum(v['count'] for v in question_counts.values())
    if total_q == 0:
        return "We couldn't detect enough questions to analyze your thinking style. Ask more questions to reveal your cognitive patterns!"

    pct = {k: (v['count'] / total_q) * 100 for k, v in question_counts.items()}

    analytical = pct.get('why', 0) + pct.get('how', 0) * 0.8
    practical = pct.get('how', 0) + pct.get('what', 0) * 0.6 + pct.get('can', 0)
    exploratory = pct.get('what', 0) + pct.get('which', 0) + pct.get('where', 0) + pct.get('when', 0)
    speculative = pct.get('would', 0) + pct.get('could', 0) + pct.get('will', 0)
    clarifying = pct.get('is', 0) + pct.get('are', 0) + pct.get('do', 0) + pct.get('does', 0)

    styles = {'analytical': analytical, 'practical': practical, 'exploratory': exploratory,
              'speculative': speculative, 'clarifying': clarifying}
    primary = max(styles, key=styles.get)
    secondary = sorted(styles, key=styles.get, reverse=True)[1]

    style_desc = {
        'analytical': "You often ask **why** and **how** questions, demonstrating a deep need to understand underlying mechanisms and root causes.",
        'practical': "Your questions lean toward **how** to accomplish tasks, indicating a pragmatic, solution-oriented mindset.",
        'exploratory': "You frequently use **what**, **which**, and location/time words, showing a curious, information-gathering approach.",
        'speculative': "You explore possibilities with **would**, **could**, and **will**, reflecting a forward-thinking, imaginative style.",
        'clarifying': "You often ask for confirmation or definitions (is, are, do, does), suggesting a methodical, detail-focused way of processing information."
    }

    profile = f"**Your thinking style is primarily {primary}.** {style_desc[primary]} "
    profile += f"As a secondary tendency, you also display a {secondary} streak. "
    profile += f"This combination suggests that you approach problems by first "
    if primary == 'analytical':
        profile += "seeking deep understanding and then moving towards practical solutions or wider exploration."
    elif primary == 'practical':
        profile += "focusing on actionable steps, occasionally stepping back to explore broader contexts or confirm details."
    elif primary == 'exploratory':
        profile += "gathering diverse information before zeroing in on specific how-to questions or verifying facts."
    elif primary == 'speculative':
        profile += "imagining future scenarios and possibilities, then grounding them with clarifying or analytical questions."
    else:
        profile += "confirming the basics and then expanding into more analytical or exploratory territory."

    profile += f" Overall, your questions span {total_q} inquiries, reflecting a rich and engaged relationship with AI."
    return profile

# ============ ARCHETYPE CLASSIFICATION ============
def classify_archetype(df, stats):
    """Classify user into an AI usage archetype."""
    total_messages = len(df)
    unique_interfaces = df['ai_interface'].nunique() if 'ai_interface' in df.columns else 0
    avg_length = df['message'].astype(str).str.len().mean() if 'message' in df.columns else 0
    avg_sentiment = stats.get('avg_sentiment', 0)
    question_ratio = stats.get('question_ratio', 0)
    
    organizing_keywords = ['organize', 'movement', 'community', 'leadership', 'coordinator', 'admin', 'mobilize']
    organizing_mentions = sum(1 for msg in df['message'].tolist()[:100] if isinstance(msg, str) and any(kw in msg.lower() for kw in organizing_keywords))
    
    if organizing_mentions > 5:
        archetype = "The Community Organizer"
        description = "You're focused on building and organizing communities. Your conversations show leadership and coordination skills."
        traits = ["Community builder", "Strategic thinker", "Organizer"]
        emoji = "🏛️"
    elif total_messages > 200 and unique_interfaces > 1:
        archetype = "The Power User"
        description = "You're an AI power user who explores multiple interfaces and pushes boundaries."
        traits = ["Multi-platform expert", "High-volume user", "Experimenter"]
        emoji = "🚀"
    elif avg_length > 100 and question_ratio > 0.4:
        archetype = "The Deep Thinker"
        description = "You ask thoughtful, complex questions and engage in deep, meaningful conversations."
        traits = ["Detailed questions", "Complex reasoning", "Thoughtful responses"]
        emoji = "🧠"
    elif avg_sentiment > 0.2 and question_ratio < 0.3:
        archetype = "The Curious Collaborator"
        description = "You use AI as a friendly collaborator, exploring ideas in a positive, engaging way."
        traits = ["Positive engagement", "Creative exploration", "Collaborative spirit"]
        emoji = "🤝"
    elif avg_length < 50 and total_messages > 50:
        archetype = "The Efficient Executor"
        description = "You're all about getting things done. Quick questions, fast answers."
        traits = ["Brief queries", "Task-focused", "Efficient"]
        emoji = "⚡"
    else:
        archetype = "The Balanced User"
        description = "You have a well-rounded approach to AI usage, combining different types of queries."
        traits = ["Versatile", "Balanced", "Adaptable"]
        emoji = "⚖️"
    
    return {'name': archetype, 'description': description, 'traits': traits, 'emoji': emoji}

def generate_wrapped_style_summary(df, stats, archetype, topics, keywords):
    """Generate Spotify Wrapped-style summary."""
    summary = {}
    if 'inserted_at' in df.columns:
        df['hour'] = pd.to_datetime(df['inserted_at']).dt.hour
        peak_hour = df['hour'].mode().iloc[0] if not df['hour'].mode().empty else 12
        if 5 <= peak_hour < 12: time_label = "Morning"
        elif 12 <= peak_hour < 17: time_label = "Afternoon"
        elif 17 <= peak_hour < 21: time_label = "Evening"
        else: time_label = "Late Night"
        summary['peak_time'] = f"{time_label} (around {peak_hour}:00)"
    else:
        summary['peak_time'] = "Various times"
    
    summary['top_topic'] = ", ".join(topics[0]['words'][:3]) if topics else "Various topics"
    summary['top_keyword'] = keywords[0][0] if keywords else "exploring"
    summary['total_messages'] = len(df)
    summary['favorite_interface'] = df['ai_interface'].mode().iloc[0] if not df['ai_interface'].mode().empty else "DeepSeek"
    
    growth = stats.get('growth_metrics', {})
    if growth.get('growth_rate', 0) > 20:
        summary['growth_trend'] = "📈 Growing rapidly!"
    elif growth.get('growth_rate', 0) > 5:
        summary['growth_trend'] = "📊 Steady growth"
    else:
        summary['growth_trend'] = "📉 Stable usage"
    
    return summary

# ============ MAIN APP ============
def main():
    st.markdown('<h1 class="main-header">🧠 AI Chat Coach</h1>', unsafe_allow_html=True)
    st.markdown("""
    <div style="text-align: center; margin-bottom: 2rem;">
        Discover your AI usage patterns, growth, and personal development journey.
        Upload your chat data for a comprehensive analysis.
    </div>
    """, unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("⚙️ Settings")
        uploaded_file = st.file_uploader("Upload JSON Chat File", type=['json'],
                                         help="Upload a JSON file containing your chat data")
        if uploaded_file:
            try:
                json_content = uploaded_file.read()
                st.session_state.raw_json = json_content
                st.session_state.file_uploaded = True
                st.info(f"📁 File size: {len(json_content) / 1024 / 1024:.2f} MB")
            except Exception as e:
                st.error(f"Error: {str(e)}")
                st.session_state.file_uploaded = False
        
        st.markdown("---")
        if st.button("🎯 Analyze Me!", type="primary", use_container_width=True):
            if st.session_state.file_uploaded:
                with st.spinner("Analyzing your AI conversations..."):
                    analyze_data(st.session_state.raw_json)
            else:
                st.warning("Please upload a JSON file first")
        
        st.markdown("---")
        st.caption("Your data stays private. No information is stored.")
    
    if st.session_state.analysis_results is not None:
        display_wrapped_analysis(st.session_state.analysis_results)
    elif st.session_state.file_uploaded:
        st.info("👈 Click 'Analyze Me!' to discover your AI usage patterns")
    else:
        st.info("👈 Upload your chat data to get started")

def analyze_data(json_content):
    """Analyze chat data and generate insights."""
    try:
        json_data = json.loads(json_content)
        df = parse_chat_json(json_data)
        if df is None or df.empty:
            st.error("Could not parse the JSON file. Please check the format.")
            return
        
        df = build_conversation_flow(df)
        st.success(f"✅ Analyzing {len(df)} messages from {df['conversation_title'].nunique()} conversations")
        
        messages = df['message'].tolist()
        sentiments = analyze_sentiment_batch(messages)
        df['sentiment_score'] = sentiments
        
        stats = {
            'total_messages': len(df),
            'unique_users': df['user'].nunique() if 'user' in df.columns else 0,
            'unique_interfaces': df['ai_interface'].nunique() if 'ai_interface' in df.columns else 0,
            'avg_sentiment': df['sentiment_score'].mean(),
            'avg_length': df['message'].astype(str).str.len().mean(),
            'conversations': df['conversation_title'].nunique()
        }
        
        question_counts, total_questions = extract_question_types(messages)
        stats['question_ratio'] = total_questions / len(df) if len(df) > 0 else 0
        cognitive_profile = generate_cognitive_profile(question_counts, stats)
        
        keywords = extract_keywords(messages, 15)
        topics = extract_topics(messages, 4, 6)
        
        # Get longest context exchanges
        long_exchanges = get_longest_context_messages(df, 5)
        
        # Get representative conversations
        longest_convs, shortest_convs = get_representative_conversations(df, 5, 5)
        
        # Generate themes summary
        themes = generate_themes_summary(question_counts, keywords, longest_convs)
        
        projects = identify_projects(messages)
        growth_metrics = calculate_growth_metrics(df)
        stats['growth_metrics'] = growth_metrics
        
        interface_stats = {}
        if 'ai_interface' in df.columns:
            for interface in df['ai_interface'].unique():
                interface_df = df[df['ai_interface'] == interface]
                interface_stats[interface] = {
                    'count': len(interface_df),
                    'avg_length': interface_df['message'].astype(str).str.len().mean(),
                    'avg_sentiment': interface_df['sentiment_score'].mean()
                }
        
        archetype = classify_archetype(df, stats)
        st.session_state.current_archetype = archetype
        summary = generate_wrapped_style_summary(df, stats, archetype, topics, keywords)
        
        st.session_state.analysis_results = {
            'df': df,
            'stats': stats,
            'keywords': keywords,
            'topics': topics,
            'projects': projects,
            'interface_stats': interface_stats,
            'archetype': archetype,
            'summary': summary,
            'question_counts': question_counts,
            'growth_metrics': growth_metrics,
            'cognitive_profile': cognitive_profile,
            'themes': themes,
            'long_exchanges': long_exchanges,
            'longest_convs': longest_convs,
            'shortest_convs': shortest_convs
        }
        
        gc.collect()
        st.success("✅ Analysis complete!")
        st.rerun()
    except Exception as e:
        st.error(f"Error: {str(e)}")

def display_wrapped_analysis(results):
    df = results['df']
    stats = results['stats']
    archetype = results['archetype']
    summary = results['summary']
    topics = results['topics']
    keywords = results['keywords']
    projects = results['projects']
    interface_stats = results['interface_stats']
    growth_metrics = results['growth_metrics']
    question_counts = results['question_counts']
    cognitive_profile = results['cognitive_profile']
    themes = results['themes']
    long_exchanges = results['long_exchanges']
    longest_convs = results['longest_convs']
    shortest_convs = results['shortest_convs']
    
    # ===== ARCHETYPE CARD =====
    st.markdown(f"""
    <div class="archetype-card">
        <div style="font-size: 3rem;">{archetype['emoji']}</div>
        <div class="archetype-name">Your AI Archetype: {archetype['name']}</div>
        <div class="archetype-desc">{archetype['description']}</div>
        <div style="margin-top: 0.5rem;">
            {'  '.join([f'<span style="background: rgba(255,255,255,0.2); padding: 0.2rem 0.8rem; border-radius: 1rem; margin: 0.2rem;">{t}</span>' for t in archetype['traits']])}
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # ===== COGNITIVE PROFILE =====
    st.markdown('<h2 class="sub-header">🧠 How You Think</h2>', unsafe_allow_html=True)
    st.markdown(f'<div class="insight-box">{cognitive_profile}</div>', unsafe_allow_html=True)
    
    # ===== QUICK STATS =====
    st.markdown('<h2 class="sub-header">📊 Your AI Usage Snapshot</h2>', unsafe_allow_html=True)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="stat-card"><div class="stat-value">{summary["total_messages"]}</div><div class="stat-label">Total Messages</div></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="stat-card"><div class="stat-value">{summary["favorite_interface"]}</div><div class="stat-label">Favorite AI</div></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="stat-card"><div class="stat-value">{summary["peak_time"]}</div><div class="stat-label">Peak Usage Time</div></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="stat-card"><div class="stat-value">{summary["growth_trend"]}</div><div class="stat-label">Usage Trend</div></div>', unsafe_allow_html=True)
    
    # ===== THEMES SECTION (NLP Summary based on questions + keywords + longest chats) =====
    st.markdown('<h2 class="sub-header">📚 Themes & Insights</h2>', unsafe_allow_html=True)
    
    if themes:
        for theme in themes:
            with st.expander(f"**{theme['theme']}** (Confidence: {theme['confidence']})"):
                st.write(theme['description'])
    else:
        st.info("Not enough data to generate themes.")
    
    # ===== REPRESENTATIVE CONVERSATIONS =====
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown('<h2 class="sub-header">📏 Top 5 Longest Conversations</h2>', unsafe_allow_html=True)
        if longest_convs:
            for i, conv in enumerate(longest_convs[:5]):
                with st.expander(f"**{conv['title'][:80]}...** ({conv['msg_count']} msgs, {conv['total_chars']:,} chars)"):
                    summary_text = generate_conversation_summary(conv)
                    st.write(f"**Summary:** {summary_text}")
                    st.write(f"**Key Terms:** {', '.join([k[0] for k in conv['keywords']])}")
                    st.write(f"**Messages:** {conv['msg_count']} | **Total Characters:** {conv['total_chars']:,}")
        else:
            st.info("No conversation data available.")
    
    with col2:
        st.markdown('<h2 class="sub-header">📏 Top 5 Shortest Conversations</h2>', unsafe_allow_html=True)
        if shortest_convs:
            for i, conv in enumerate(shortest_convs[:5]):
                with st.expander(f"**{conv['title'][:80]}...** ({conv['msg_count']} msgs, {conv['total_chars']:,} chars)"):
                    summary_text = generate_conversation_summary(conv)
                    st.write(f"**Summary:** {summary_text}")
                    st.write(f"**Key Terms:** {', '.join([k[0] for k in conv['keywords']])}")
                    st.write(f"**Messages:** {conv['msg_count']} | **Total Characters:** {conv['total_chars']:,}")
        else:
            st.info("No conversation data available.")
    
    # ===== QUESTION TYPES WITH EXPANDABLE EXAMPLES =====
    st.markdown('<h2 class="sub-header">❓ How You Ask Questions</h2>', unsafe_allow_html=True)
    
    if question_counts and sum(v['count'] for v in question_counts.values()) > 0:
        # Create bar chart
        q_df = pd.DataFrame([
            {'Type': k.capitalize(), 'Count': v['count']}
            for k, v in question_counts.items() if v['count'] > 0
        ]).sort_values('Count', ascending=False).head(10)
        
        if not q_df.empty:
            fig = px.bar(q_df, x='Count', y='Type', orientation='h', title="Question Types")
            fig.update_layout(height=300, yaxis={'categoryorder': 'total ascending'})
            st.plotly_chart(fig, use_container_width=True)
        
        # Show examples for top question types
        st.markdown("### 📝 Example Questions by Type")
        top_types = sorted(question_counts.items(), key=lambda x: x[1]['count'], reverse=True)[:5]
        
        for q_type, q_data in top_types:
            if q_data['examples']:
                with st.expander(f"**{q_type.capitalize()} Questions** ({q_data['count']} total)"):
                    for i, example in enumerate(q_data['examples']):
                        st.markdown(f'<div class="message-card user"><strong>Example {i+1}:</strong><br>{example}</div>', unsafe_allow_html=True)
    else:
        st.info("No questions detected")
    
    # ===== LONGEST CONTEXT EXCHANGES =====
    if long_exchanges:
        st.markdown('<h2 class="sub-header">💬 Deepest Conversations</h2>', unsafe_allow_html=True)
        st.markdown("*Your longest and most detailed exchanges, showing where you engage most deeply with AI.*")
        
        for i, exchange in enumerate(long_exchanges[:5]):
            with st.expander(f"**Exchange {i+1}** from '{exchange['conversation_title'][:60]}...' ({exchange['combined_length']:,} total chars)"):
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown('<div class="message-card user"><strong>Your Message:</strong><br>' + 
                              exchange['user_message'][:500] + ('...' if len(exchange['user_message']) > 500 else '') + 
                              f'<br><small>({exchange["user_message_length"]:,} chars)</small></div>', 
                              unsafe_allow_html=True)
                with col2:
                    st.markdown('<div class="message-card ai"><strong>AI Response:</strong><br>' + 
                              exchange['ai_response'][:500] + ('...' if len(exchange['ai_response']) > 500 else '') + 
                              f'<br><small>({exchange["ai_response_length"]:,} chars)</small></div>', 
                              unsafe_allow_html=True)
    
    # ===== TOP KEYWORDS =====
    st.markdown('<h2 class="sub-header">🔑 Key Keywords</h2>', unsafe_allow_html=True)
    if keywords:
        keyword_df = pd.DataFrame(keywords, columns=['Word', 'Frequency'])
        fig = px.bar(keyword_df.head(10), x='Frequency', y='Word', orientation='h', title="Most Used Words")
        fig.update_layout(height=300, yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(fig, use_container_width=True)
    
    # ===== TIMELINE WITH DATE FILTER =====
    st.markdown('<h2 class="sub-header">📅 Activity Timeline</h2>', unsafe_allow_html=True)
    if 'inserted_at' in df.columns and not df.empty:
        df_timeline = df.copy()
        df_timeline['inserted_at'] = pd.to_datetime(df_timeline['inserted_at'], errors='coerce')
        df_timeline = df_timeline.dropna(subset=['inserted_at'])
        if not df_timeline.empty:
            min_date = df_timeline['inserted_at'].min().date()
            max_date = df_timeline['inserted_at'].max().date()
            
            col1, col2 = st.columns(2)
            with col1:
                start_date = st.date_input("Start date", min_date, min_value=min_date, max_value=max_date)
            with col2:
                end_date = st.date_input("End date", max_date, min_value=min_date, max_value=max_date)
            
            if start_date > end_date:
                st.error("Start date must be before end date.")
            else:
                mask = (df_timeline['inserted_at'].dt.date >= start_date) & (df_timeline['inserted_at'].dt.date <= end_date)
                filtered = df_timeline[mask]
                if filtered.empty:
                    st.info("No activity in selected range.")
                else:
                    daily_counts = filtered.groupby(filtered['inserted_at'].dt.date).size().reset_index(name='count')
                    fig = px.bar(daily_counts, x='inserted_at', y='count', title="Messages per Day")
                    fig.update_layout(xaxis_title="Date", yaxis_title="Messages")
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No date information available.")
    
    # ===== INTERFACE COMPARISON =====
    if interface_stats and len(interface_stats) > 1:
        st.markdown('<h2 class="sub-header">🤖 Interface Comparison</h2>', unsafe_allow_html=True)
        interface_df = pd.DataFrame([{'Interface': k, 'Messages': v['count'], 'Avg Length': v['avg_length'], 'Avg Sentiment': v['avg_sentiment']} for k, v in interface_stats.items()]).sort_values('Messages', ascending=False)
        fig = make_subplots(specs=[[{"secondary_y": True}]])
        fig.add_trace(go.Bar(x=interface_df['Interface'], y=interface_df['Messages'], name="Messages", marker_color='#6C63FF'), secondary_y=False)
        fig.add_trace(go.Scatter(x=interface_df['Interface'], y=interface_df['Avg Sentiment'], name="Avg Sentiment", mode='lines+markers', marker_color='#FF6B6B'), secondary_y=True)
        fig.update_layout(title="AI Interface Usage", xaxis_title="Interface")
        fig.update_yaxes(title_text="Messages", secondary_y=False)
        fig.update_yaxes(title_text="Avg Sentiment", secondary_y=True, range=[-1, 1])
        st.plotly_chart(fig, use_container_width=True)
    
    # ===== GROWTH INSIGHTS =====
    st.markdown('<h2 class="sub-header">📈 Your Growth Journey</h2>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    with col1:
        growth_pct = growth_metrics.get('growth_rate', 0)
        st.markdown(f'<div class="stat-card"><div style="font-size: 2rem;">📈</div><div class="stat-value">{growth_pct:+.0f}%</div><div class="stat-label">Activity Change</div></div>', unsafe_allow_html=True)
    with col2:
        sentiment_change = growth_metrics.get('sentiment_change', 0)
        st.markdown(f'<div class="stat-card"><div style="font-size: 2rem;">😊</div><div class="stat-value">{sentiment_change:+.2f}</div><div class="stat-label">Sentiment Change</div></div>', unsafe_allow_html=True)
    with col3:
        question_growth = growth_metrics.get('question_growth', 0)
        st.markdown(f'<div class="stat-card"><div style="font-size: 2rem;">🧐</div><div class="stat-value">{question_growth:+.0f}%</div><div class="stat-label">Curiosity Change</div></div>', unsafe_allow_html=True)
    
    # ===== RECOMMENDATIONS =====
    st.markdown('<h2 class="sub-header">💡 Personal Development Insights</h2>', unsafe_allow_html=True)
    recommendations = []
    if "Community Organizer" in archetype['name']:
        recommendations.append("🏛️ Your community building skills are strong! Consider documenting your organizing strategies.")
    elif "Power User" in archetype['name']:
        recommendations.append("🔮 You're already a power user! Consider building custom AI workflows and automations.")
    elif "Deep Thinker" in archetype['name']:
        recommendations.append("🧠 Your deep questions are valuable. Try journaling your insights after each conversation.")
    elif "Curious Collaborator" in archetype['name']:
        recommendations.append("🤝 You're great at collaboration. Try using AI for brainstorming and creative projects.")
    elif "Efficient Executor" in archetype['name']:
        recommendations.append("⚡ You're efficient! Consider exploring deeper, more creative use cases.")
    else:
        recommendations.append("🌱 You're on a journey! Try different AI interfaces to find what works best for you.")
    if topics:
        top_words = topics[0]['words'][:3]
        recommendations.append(f"📚 Your top topics include {', '.join(top_words)}. Consider diving deeper into one of these areas.")
    if stats['total_messages'] > 50:
        recommendations.append("📊 You have enough data for meaningful analysis. Keep tracking your progress!")
    for rec in recommendations[:3]:
        st.markdown(f'<div class="insight-box">{rec}</div>', unsafe_allow_html=True)
    
    # ===== DOWNLOAD =====
    st.markdown('<h2 class="sub-header">💾 Download Your Insights</h2>', unsafe_allow_html=True)
    report_data = {
        'Archetype': archetype['name'], 'Archetype Description': archetype['description'],
        'Total Messages': stats['total_messages'], 'Favorite AI': summary['favorite_interface'],
        'Peak Usage': summary['peak_time'], 'Top Topic': summary['top_topic'],
        'Top Keyword': summary['top_keyword'], 'Growth Trend': summary['growth_trend'],
        'Avg Sentiment': f"{stats['avg_sentiment']:.2f}", 'Question Ratio': f"{stats['question_ratio']:.1%}",
        'Conversations': stats.get('conversations', 0)
    }
    report_df = pd.DataFrame([report_data])
    csv = report_df.to_csv(index=False).encode('utf-8')
    col1, col2 = st.columns(2)
    with col1:
        st.download_button("📥 Download Summary Report (CSV)", data=csv,
                           file_name=f"ai_coach_report_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")
    with col2:
        full_csv = df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Download Full Analysis Data (CSV)", data=full_csv,
                           file_name=f"ai_coach_full_data_{datetime.now().strftime('%Y%m%d')}.csv", mime="text/csv")

if __name__ == "__main__":
    main()
