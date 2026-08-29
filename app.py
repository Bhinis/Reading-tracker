import io
import os
from datetime import datetime
import pandas as pd
from PIL import Image, ImageDraw, ImageFont
import requests
import streamlit as st

DATA_FILE = "reading_log.csv"

# ---------------------------------------------------------
# 1. DATA STORAGE & INITIALIZATION
# ---------------------------------------------------------
def load_data():
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(
            columns=[
                "date", "book", "author", "pages", "days_taken", 
                "genre", "mood", "rating", "cover_url",
            ]
        )
        df.to_csv(DATA_FILE, index=False)
        return df
    return pd.read_csv(DATA_FILE)

def save_entry(entry_dict):
    df = load_data()
    df = pd.concat([df, pd.DataFrame([entry_dict])], ignore_index=True)
    df.to_csv(DATA_FILE, index=False)

# ---------------------------------------------------------
# 2. IMAGE GENERATION (PILLOW)
# ---------------------------------------------------------
def generate_wrapped_image(stats):
    canvas_w, canvas_h = 1080, 1920

    if os.path.exists("background.jpg"):
        base_img = Image.open("background.jpg").convert("RGBA").resize((canvas_w, canvas_h))
    else:
        base_img = Image.new("RGBA", (canvas_w, canvas_h), color="#EFE9E1")

    overlay = Image.new("RGBA", (canvas_w, canvas_h), (255, 255, 255, 110))
    img = Image.alpha_composite(base_img, overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    try:
        f_year = ImageFont.truetype("font.ttf", 42)
        f_title = ImageFont.truetype("font.ttf", 78)
        f_stat_num = ImageFont.truetype("font.ttf", 64)
        f_stat_label = ImageFont.truetype("font.ttf", 26)
        f_text = ImageFont.truetype("font.ttf", 34)
        f_text_bold = ImageFont.truetype("font.ttf", 36)
    except Exception:
        f_year = f_title = f_stat_num = f_stat_label = f_text = f_text_bold = ImageFont.load_default()

    text_color = "#3B1E1E"

    # Header
    draw.text((canvas_w // 2, 220), str(datetime.now().year), fill=text_color, font=f_year, anchor="mm")
    draw.text((canvas_w // 2, 290), "My Reading Wrapped", fill=text_color, font=f_title, anchor="mm")

    # Top Metrics
    col_x = [230, canvas_w // 2, 850]
    draw.text((col_x[0], 450), str(stats["books"]), fill=text_color, font=f_stat_num, anchor="mm")
    draw.text((col_x[0], 510), "BOOKS READ", fill=text_color, font=f_stat_label, anchor="mm")

    draw.text((col_x[1], 450), f"{stats['pages']:,}", fill=text_color, font=f_stat_num, anchor="mm")
    draw.text((col_x[1], 510), "PAGES READ", fill=text_color, font=f_stat_label, anchor="mm")

    draw.text((col_x[2], 450), str(stats["entries"]), fill=text_color, font=f_stat_num, anchor="mm")
    draw.text((col_x[2], 510), "ENTRIES", fill=text_color, font=f_stat_label, anchor="mm")

    # Book Cover
    cover_w, cover_h = 320, 480
    cover_x = (canvas_w - cover_w) // 2
    cover_y = 670

    if stats["cover_url"]:
        try:
            if stats["cover_url"].startswith("http"): 
                res = requests.get(stats["cover_url"], timeout=5)
                book_img = Image.open(io.BytesIO(res.content)).convert("RGB").resize((cover_w, cover_h))
            else: 
                book_img = Image.open(stats["cover_url"]).convert("RGB").resize((cover_w, cover_h))
            img.paste(book_img, (cover_x, cover_y))
        except Exception as e:
            print(f"Could not load image: {e}")

    # Helper function to prevent text from overlapping the book cover
    def truncate(text, length=15):
        text = str(text)
        return text if len(text) <= length else text[:length-3] + '...'

    # Expanded Stats List
    left_labels = [
        "Top Genre", 
        "Top Author", 
        "Top Rated Book", 
        "Longest Book", 
        "Average Pace",
        "Average Rating", 
        "Best Streak"
    ]
    
    right_values = [
        stats["top_genre"], 
        truncate(stats["top_author"]),
        truncate(stats["top_book"]), 
        truncate(stats["longest_book"]),
        f"{stats['avg_pace']} pgs/day",
        f"{stats['avg_rating']} / 5", 
        f"{stats['streak']} days"
    ]

    # Draw the stats list vertically around the cover
    y_pos = 680
    for label, val in zip(left_labels, right_values):
        draw.text((90, y_pos), label, fill="#665555", font=f_text, anchor="lm")
        draw.text((990, y_pos), str(val), fill=text_color, font=f_text_bold, anchor="rm")
        y_pos += 80

    output = io.BytesIO()
    img.save(output, format="PNG")
    return output.getvalue()

# ---------------------------------------------------------
# 3. STATS COMPUTATION
# ---------------------------------------------------------
def compute_stats(df):
    if df.empty:
        return {
            "books": 0, "pages": 0, "entries": 0, "top_genre": "-", "top_mood": "-", 
            "avg_rating": 0, "streak": 0, "cover_url": None, "top_book": "-", 
            "longest_book": "-", "top_author": "-", "avg_pace": 0
        }

    total_pages = int(df["pages"].sum())
    unique_books = int(df["book"].nunique())
    total_entries = len(df)
    
    # Existing basic stats
    top_genre = df["genre"].mode()[0] if not df["genre"].dropna().empty else "N/A"
    top_mood = df["mood"].mode()[0] if not df["mood"].dropna().empty else "N/A"
    avg_rating = round(df["rating"].mean(), 1) if not df["rating"].empty else 0

    # New interesting stats
    top_book = df.loc[df['rating'].idxmax()]['book'] if not pd.isna(df['rating'].max()) else "N/A"
    longest_book = df.loc[df['pages'].idxmax()]['book'] if not pd.isna(df['pages'].max()) else "N/A"
    top_author = df["author"].mode()[0] if not df["author"].dropna().empty else "N/A"
    
    total_days = df["days_taken"].sum() if "days_taken" in df.columns else 0
    avg_pace = round(total_pages / total_days) if total_days > 0 else 0

    # Streak Logic
    dates = pd.to_datetime(df["date"]).drop_duplicates().sort_values().to_list()
    streak = 1 if len(dates) > 0 else 0
    max_streak = streak
    for i in range(1, len(dates)):
        if (dates[i] - dates[i - 1]).days == 1:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 1

    last_cover = df["cover_url"].dropna().iloc[-1] if not df["cover_url"].dropna().empty else None

    return {
        "books": unique_books, "pages": total_pages, "entries": total_entries,
        "top_genre": top_genre, "top_mood": top_mood, "avg_rating": avg_rating,
        "streak": max_streak, "cover_url": last_cover, 
        "top_book": top_book, "longest_book": longest_book, 
        "top_author": top_author, "avg_pace": avg_pace
    }

# ---------------------------------------------------------
# 4. STREAMLIT USER INTERFACE
# ---------------------------------------------------------
st.set_page_config(page_title="Reading Tracker", page_icon="📖")
st.title("📖 Reading Tracker & Wrapped")

tab1, tab2, tab3 = st.tabs(["Log Session", "My Data", "Reading Wrapped"])

with tab1:
    st.subheader("Log a Reading Session")
    with st.form("log_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            date_read = st.date_input("Date Finished")
            book_name = st.text_input("Book Title *")
            pages_read = st.number_input("Pages Read *", min_value=1, step=1, value=300)
            genre = st.selectbox("Genre", ["Fiction", "Non-Fiction", "Sci-Fi / Fantasy", "Mystery / Thriller", "Biography", "Self-Help"])
        
        with col2:
            days_taken = st.number_input("Days Taken to Read", min_value=1, step=1, value=7)
            author_name = st.text_input("Author")
            mood = st.selectbox("Mood", ["Dark", "Inspiring", "Adventurous", "Emotional", "Mysterious", "Relaxed"])
            rating = st.slider("Rating", 1.0, 5.0, 4.0, 0.5)

        st.write("Cover Image (Choose one)")
        uploaded_cover = st.file_uploader("Upload an Image from your computer", type=["jpg", "png", "jpeg"])
        cover_link = st.text_input("OR paste an Image URL (e.g., from OpenLibrary/Google)")
        
        submitted = st.form_submit_button("Save Entry")

        if submitted:
            if book_name.strip():
                final_cover_path = ""
                
                if uploaded_cover is not None:
                    os.makedirs("covers", exist_ok=True)
                    clean_name = "".join(x for x in book_name if x.isalnum())
                    ext = uploaded_cover.name.split(".")[-1]
                    final_cover_path = f"covers/{clean_name}.{ext}"
                    with open(final_cover_path, "wb") as f:
                        f.write(uploaded_cover.getbuffer())
                elif cover_link.strip():
                    final_cover_path = cover_link.strip()

                save_entry({
                    "date": date_read.strftime("%Y-%m-%d"),
                    "book": book_name,
                    "author": author_name,
                    "pages": pages_read,
                    "days_taken": days_taken,
                    "genre": genre,
                    "mood": mood,
                    "rating": rating,
                    "cover_url": final_cover_path,
                })
                st.success("Entry saved successfully!")
            else:
                st.error("Please enter a book title.")

with tab2:
    st.subheader("Reading Log")
    df = load_data()
    st.dataframe(df, use_container_width=True)

with tab3:
    st.subheader("Generate Wrapped Card")
    df = load_data()
    stats = compute_stats(df)

    if st.button("Generate Card"):
        img_bytes = generate_wrapped_image(stats)
        st.image(img_bytes, caption="Your Reading Wrapped", use_container_width=True)
        st.download_button(label="Download Card (PNG)", data=img_bytes, file_name=f"reading_wrapped_{datetime.now().year}.png", mime="image/png")