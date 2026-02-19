import streamlit as st
from notion_client import Client
import cloudinary.uploader
import cloudinary
from datetime import datetime, timedelta

# --- 1. CONFIGURATION & SECRETS ---
st.set_page_config(page_title="Garage Freezer Tracker", page_icon="🧊", layout="wide")

try:
    # Notion Credentials
    notion = Client(auth=st.secrets["FREEZER_NOTION_TOKEN"])
    DATABASE_ID = st.secrets["FREEZER_NOTION_DATABASE_ID"]

    # Cloudinary Credentials
    cloudinary.config(
        cloud_name=st.secrets["CLOUDINARY_CLOUD_NAME"],
        api_key=st.secrets["CLOUDINARY_API_KEY"],
        api_secret=st.secrets["CLOUDINARY_API_SECRET"]
    )
except Exception as e:
    st.error("❌ Missing Secrets! Check your Streamlit Cloud Settings.")
    st.stop()

# --- 2. HELPER FUNCTIONS ---
def add_freezer_item(food_name, expiry_date, added_by, estimated_value, notes="", photo_file=None):
    """Sends new freezer item data to Notion"""
    try:
        image_url = None
        if photo_file:
            upload_result = cloudinary.uploader.upload(photo_file)
            image_url = upload_result["secure_url"]

        new_page = {
            "parent": {"database_id": DATABASE_ID},
            "properties": {
                "Food": {"title": [{"text": {"content": food_name}}]},
                "Date Added": {"date": {"start": datetime.now().date().isoformat()}},
                "Expires": {"date": {"start": expiry_date.isoformat()}},
                "Est Cost": {"number": estimated_value},
                "Added By": {"select": {"name": added_by}},
                "Notes": {"rich_text": [{"text": {"content": notes}}]},
                "Archived": {"checkbox": False}
            }
        }

        if image_url:
            new_page["properties"]["Photo"] = {
                "files": [{"name": f"Photo_{food_name}", "type": "external", "external": {"url": image_url}}]
            }

        notion.pages.create(**new_page)
        return True, "Added to the freezer!"
    except Exception as e:
        return False, str(e)

# --- 3. UI - ADD NEW ITEM ---
st.title("🧊 Garage Freezer Tracker")

with st.form("add_form", clear_on_submit=True):
    col1, col2 = st.columns(2)

    with col1:
        food_name = st.text_input("What food is it?")
        photo_file = st.file_uploader("📸 Take or upload a photo", type=["jpg", "jpeg", "png"])

    with col2:
        added_by = st.selectbox("Who added it?", ["You", "Wife"])
        # Default expiry is 3 months out for freezer items
        default_expiry = datetime.now().date() + timedelta(days=90)
        expiry_date = st.date_input("Expiration Date", min_value=datetime.now().date(), value=default_expiry)
        estimated_value = st.number_input("Est Cost ($)", min_value=0.0, value=10.0, step=0.50)
        notes = st.text_area("Notes")

    if st.form_submit_button("Add to Freezer"):
        if food_name:
            success, msg = add_freezer_item(food_name, expiry_date, added_by, estimated_value, notes, photo_file)
            if success:
                st.success(msg)
                st.balloons()
            else:
                st.error(f"Error: {msg}")
        else:
            st.warning("Please enter a food name.")

# --- 4. UI - FREEZER VIEW & VERDICT ---
st.divider()
st.header("🔍 Current Freezer Inventory")

# Query only non-archived items
results = notion.databases.query(
    database_id=DATABASE_ID,
    filter={"property": "Archived", "checkbox": {"equals": False}}
).get("results")

if not results:
    st.info("The freezer is empty! Time to stock up.")
else:
    for page in results:
        p = page.get("properties", {})
        item_id = page["id"]

        # --- Safe Data Extraction ---
        food_title_list = p.get("Food", {}).get("title", [])
        food = food_title_list[0]["text"]["content"] if food_title_list else "Unknown Food"

        cost_prop = p.get("Est Cost", {}).get("number")
        cost = cost_prop if cost_prop is not None else 0.0

        status = p.get("Status", {}).get("formula", {}).get("string", "No Status")
        days_left = p.get("Days Left", {}).get("formula", {}).get("string", "N/A")

        photo_files = p.get("Photo", {}).get("files", [])
        photo = photo_files[0].get("external", {}).get("url") if photo_files else None

        user_prop = p.get("Added By", {}).get("select")
        user = user_prop["name"] if user_prop else "Unknown"

        # --- UI Display ---
        with st.container():
            c1, c2, c3 = st.columns([1, 2, 1])
            with c1:
                if photo:
                    st.image(photo, width=150)
                else:
                    st.write("📷 No photo")
            with c2:
                st.subheader(food)
                st.write(f"👤 {user}")
                st.write(f"**Status:** {status} ({days_left})")
                st.write(f"💰 **Value:** ${cost:.2f}")
            with c3:
                st.write("⚖️ **Verdict?**")

                if st.button("🍴 Used", key=f"eat_{item_id}"):
                    notion.pages.update(page_id=item_id, properties={
                        "Verdict": {"select": {"name": "Used"}},
                        "Archived": {"checkbox": True}
                    })
                    st.rerun()

                if st.button("🗑️ Tossed", key=f"toss_{item_id}"):
                    notion.pages.update(page_id=item_id, properties={
                        "Verdict": {"select": {"name": "Tossed"}},
                        "Archived": {"checkbox": True}
                    })
                    st.rerun()

        st.divider()
