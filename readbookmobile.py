import flet as ft
import pymupdf as fitz
import os
import json
import base64
import requests
import threading
import tempfile
from supabase import create_client, Client

BOT_TOKEN = "8876009144:AAH2txX37Vzwp1Tu6O_YnSemAG1imamx4L4"
SUPABASE_URL = "https://imylliwshodkqytjnlqs.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImlteWxsaXdzaG9ka3F5dGpubHFzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTE3MzIxMzUsImV4cCI6MjEwNzMwODEzNX0.nIJ2XSFry_ZEkL1KjO10DhNM4cBFVkw-4rGA4tNblvU"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
PROGRESS_FILE = "reading_progress.json"
COVER_CACHE_FILE = "cover_cache.json"
ZOOM_FILE = "zoom_prefs.json"

TEMP_DIR = tempfile.TemporaryDirectory()

def load_cover_cache():
    if os.path.exists(COVER_CACHE_FILE):
        try:
            with open(COVER_CACHE_FILE, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_cover_cache(cache_data):
    try:
        with open(COVER_CACHE_FILE, "w") as f: json.dump(cache_data, f)
    except: pass

cover_cache = load_cover_cache()

def load_zoom():
    if os.path.exists(ZOOM_FILE):
        try:
            with open(ZOOM_FILE, "r") as f: return json.load(f).get("zoom", 1.0)
        except: return 1.0
    return 1.0

def save_zoom(zoom_val):
    try:
        with open(ZOOM_FILE, "w") as f: json.dump({"zoom": zoom_val}, f)
    except: pass

def load_progress(book_name):
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r") as f: return json.load(f).get(book_name, 0)
        except: return 0
    return 0

def save_progress(book_name, page_num):
    data = {}
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r") as f: data = json.load(f)
        except: pass
    
    if page_num <= 0:
        if book_name in data:
            del data[book_name]
    else:
        data[book_name] = page_num
        
    try:
        with open(PROGRESS_FILE, "w") as f: json.dump(data, f)
    except: pass

def get_recent_books():
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r") as f:
                data = json.load(f)
                return [book for book, page in data.items() if page > 0]
        except: return []
    return []

def get_cloud_books():
    cloud_books = {}
    try:
        response = supabase.table("cloud_books").select("file_name, file_id, cover_file_id, category").execute()
        for row in response.data:
            cat = row.get("category")
            if not cat or str(cat).strip() == "":
                cat = "ទូទៅ"
            cloud_books[row["file_name"]] = {
                "file_id": row["file_id"],
                "cover_photo_id": row.get("cover_file_id"),
                "category": cat
            }
    except Exception as e:
        print("Error fetching from Supabase:", e)
    return cloud_books

def download_to_temp(file_id, pdf_name):
    try:
        temp_file_path = os.path.join(TEMP_DIR.name, pdf_name)
        if os.path.exists(temp_file_path):
            return temp_file_path
            
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        res = requests.get(url).json()
        if res["ok"]:
            file_path = res["result"]["file_path"]
            download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
            pdf_data = requests.get(download_url)
            with open(temp_file_path, "wb") as f:
                f.write(pdf_data.content)
            return temp_file_path
    except Exception as e:
        print("Download Error:", e)
    return None

def main(page: ft.Page):
    page.title = "បណ្ណាល័យអានសៀវភៅ"
    page.window_width = 1100
    page.window_height = 800
    page.window_resizable = True
    page.window_maximizable = True
    page.theme_mode = ft.ThemeMode.LIGHT
    page.bgcolor = ft.colors.BLUE_GREY_50
    page.padding = 15
    
    page.current_view = "library" 
    current_font_size = 14

    recent_grid = ft.Row(scroll=ft.ScrollMode.ADAPTIVE, spacing=15) 
    # ប្រើ max_extent ដើម្បីឱ្យ Grid ស្របតាមអេក្រង់ទូរសព្ទនិងកុំព្យូទ័រស្វ័យប្រវត្តិ
    all_books_grid = ft.GridView(expand=True, max_extent=140, child_aspect_ratio=0.7, spacing=15, run_spacing=15)

    def create_book_card(pdf_name, book_data, is_recent=False):
        photo_id = book_data.get("cover_photo_id")
        
        img_container = ft.Container(
            content=ft.ProgressRing(width=25, height=25, stroke_width=2), 
            expand=True, 
            alignment=ft.alignment.center, 
            bgcolor=ft.colors.GREY_200,
            padding=0, 
            margin=ft.margin.only(top=5, left=5, right=5, bottom=0) 
        )

        def fetch_and_update_image():
            if not photo_id:
                img_container.content = ft.Icon(ft.icons.MENU_BOOK, size=40, color=ft.colors.BLUE_400)
                if img_container.page:
                    img_container.update()
                return
            
            url = None
            if photo_id in cover_cache:
                url = cover_cache[photo_id]
            else:
                try:
                    res = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={photo_id}").json()
                    if res.get("ok"):
                        url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{res['result']['file_path']}"
                        cover_cache[photo_id] = url
                        save_cover_cache(cover_cache)
                except:
                    pass
                    
            if url:
                img_container.content = ft.Image(src=url, fit=ft.ImageFit.COVER, expand=True, width=float('inf'), border_radius=6)
            else:
                img_container.content = ft.Icon(ft.icons.MENU_BOOK, size=40, color=ft.colors.BLUE_400)
                
            if img_container.page:
                img_container.update()

        threading.Thread(target=fetch_and_update_image, daemon=True).start()

        card_width = 130 if is_recent else None
        card_height = 190 if is_recent else None

        return ft.Card(
            elevation=4,
            width=card_width,
            height=card_height,
            content=ft.Container(
                bgcolor=ft.colors.WHITE,
                padding=0, 
                content=ft.Column(
                    spacing=0, 
                    controls=[
                        img_container,
                        ft.Container(
                            content=ft.Text(pdf_name, weight="bold", size=13, text_align="center", max_lines=2, overflow=ft.TextOverflow.ELLIPSIS), 
                            padding=8, 
                            alignment=ft.alignment.center,
                            bgcolor=ft.colors.WHITE 
                        )
                    ]
                ),
                on_click=lambda e, name=pdf_name, fid=book_data["file_id"], p_id=photo_id: show_reader(name, fid, cover_cache.get(p_id) if p_id else None),
                border_radius=8, ink=True
            )
        )

    def show_library():
        page.current_view = "library"
        page.on_resize = None 
        page.controls.clear()
        
        cloud_books = get_cloud_books()
        recent_books_list = get_recent_books()
        total_books = len(cloud_books)
        
        book_count_text = ft.Text(f"សរុប: {total_books} ក្បាល", weight="bold", size=14, color=ft.colors.BLUE_GREY_700)
        
        all_categories = ["ទាំងអស់"] + sorted(list(set(b["category"] for b in cloud_books.values())))
        
        category_dropdown = ft.Dropdown(
            label="ប្រភេទ",
            value="ទាំងអស់",
            width=150,
            height=40,
            text_size=13,
            content_padding=10,
            options=[ft.dropdown.Option(c) for c in all_categories],
            on_change=lambda e: populate_grids(search_field.value, category_dropdown.value, cloud_books, recent_books_list, book_count_text)
        )

        search_field = ft.TextField(
            hint_text="ស្វែងរកសៀវភៅ...", 
            prefix_icon=ft.icons.SEARCH,
            on_change=lambda e: populate_grids(e.control.value, category_dropdown.value, cloud_books, recent_books_list, book_count_text),
            border_radius=20, 
            filled=True, 
            bgcolor=ft.colors.WHITE,
            width=200, 
            height=40,
            content_padding=10
        )

        def zoom_in(e):
            nonlocal current_font_size
            if current_font_size < 22:
                current_font_size += 2
                populate_grids(search_field.value, category_dropdown.value, cloud_books, recent_books_list, book_count_text)

        def zoom_out(e):
            nonlocal current_font_size
            if current_font_size > 10:
                current_font_size -= 2
                populate_grids(search_field.value, category_dropdown.value, cloud_books, recent_books_list, book_count_text)
        
        zoom_controls = ft.Row([
            ft.IconButton(ft.icons.ZOOM_OUT, icon_size=18, on_click=zoom_out, tooltip="បង្រួមអក្សរ"),
            ft.IconButton(ft.icons.ZOOM_IN, icon_size=18, on_click=zoom_in, tooltip="ពង្រីកអក្សរ")
        ], spacing=0)
        
        header_row = ft.ResponsiveRow([
            ft.Row([
                ft.Text("អាន២៤", size=24, weight="bold", color=ft.colors.BLUE_GREY_900),
                ft.IconButton(ft.icons.REFRESH, icon_size=20, on_click=lambda e: show_library(), tooltip="ទាញសៀវភៅថ្មីៗពី Cloud"),
                zoom_controls
            ], col={"xs": 12, "md": 6}),
            ft.Row([
                category_dropdown, 
                book_count_text, 
                search_field
            ], spacing=10, alignment=ft.MainAxisAlignment.END, col={"xs": 12, "md": 6})
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN, vertical_alignment=ft.CrossAxisAlignment.CENTER)

        recent_section = ft.Column([
            ft.Text("កំពុងអានថ្មីៗ", size=16, weight="bold", color=ft.colors.ORANGE_700),
            ft.Container(content=recent_grid, height=200, padding=ft.padding.only(bottom=5)),
            ft.Divider(height=1, color=ft.colors.GREY_300)
        ], visible=False) 

        all_section = ft.Column([
            ft.Text("សៀវភៅទាំងអស់", size=16, weight="bold", color=ft.colors.BLUE_GREY_800),
            ft.Container(height=5),
            all_books_grid
        ], expand=True)

        page.recent_section_ref = recent_section

        page.add(
            ft.Column([
                header_row,
                ft.Container(height=5),
                recent_section,
                all_section
            ], expand=True)
        )
        
        populate_grids("", "ទាំងអស់", cloud_books, recent_books_list, book_count_text)

    def populate_grids(search_text, selected_category, cloud_books, recent_books_list, count_text_control):
        recent_grid.controls.clear()
        all_books_grid.controls.clear()
        
        visible_count = 0
        has_recent = False
        
        for pdf_name, book_data in cloud_books.items():
            match_category = (selected_category == "ទាំងអស់" or book_data["category"] == selected_category)
            match_search = (search_text.lower() in pdf_name.lower())

            if match_category and match_search:
                visible_count += 1
                all_books_grid.controls.append(create_book_card(pdf_name, book_data, is_recent=False))
                
                if pdf_name in recent_books_list and search_text == "" and selected_category == "ទាំងអស់": 
                    recent_grid.controls.append(create_book_card(pdf_name, book_data, is_recent=True))
                    has_recent = True
                
                page.update() 
        
        if hasattr(page, 'recent_section_ref'):
            page.recent_section_ref.visible = has_recent and (selected_category == "ទាំងអស់")

        count_text_control.value = f"សរុប: {visible_count} ក្បាល"
        page.update()

    def show_reader(pdf_name, file_id, cover_url=None):
        page.current_view = "reader"
        page.controls.clear()
        page.update() 
        
        loading_controls = []
        if cover_url:
            loading_controls.append(ft.Image(src=cover_url, height=220, fit=ft.ImageFit.CONTAIN, border_radius=8))
            
        loading_controls.extend([
            ft.Container(height=15),
            ft.ProgressRing(), 
            ft.Container(height=10),
            ft.Text("กำลังโหลดសៀវភៅ...", size=18)
        ])
        
        loading_view = ft.Column(loading_controls, alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER)
        
        page.add(ft.Container(content=loading_view, expand=True, alignment=ft.alignment.center))
        page.update()
        
        temp_path = download_to_temp(file_id, pdf_name)
        page.controls.clear()
        
        if not temp_path:
            page.add(ft.Column([
                ft.Text("បរាជ័យក្នុងការទាញយកសៀវភៅ។", color="red"),
                ft.ElevatedButton("ត្រឡប់ក្រោយ", on_click=lambda e: show_library())
            ]))
            page.update()
            return

        try:
            doc = fitz.open(temp_path)
            total_pages = len(doc)
        except Exception as e:
            page.controls.clear()
            page.add(ft.Column([
                ft.Text(f"Error បើកឯកសារ: {e}", color="red"),
                ft.ElevatedButton("ត្រឡប់ក្រោយ", on_click=lambda e: show_library())
            ]))
            page.update()
            return

        current_page = load_progress(pdf_name)
        
        # ពិនិត្យថាជា Mobile ឬ Desktop (ຖ້າអេក្រង់តូចជាង 768px ຖືថា Mobile គឺបង្ហាញ ១ ទំព័រ)
        def is_mobile_screen():
            return (page.width is not None and page.width < 768)

        if not is_mobile_screen():
            if current_page % 2 != 0: current_page -= 1
        
        if current_page >= total_pages or current_page < 0: current_page = 0

        page_text = ft.Text("", size=14, weight="bold", color=ft.colors.BLUE_GREY_900)

        pdf_zoom = load_zoom() 
        base_page_width = 380 
        zoom_text_display = ft.Text(f"{int(pdf_zoom * 100)}%", weight="bold", size=13, color=ft.colors.BLUE_GREY_900)

        def get_page_image(page_num):
            if page_num < 0 or page_num >= total_pages: return None
            pdf_page = doc.load_page(page_num)
            pix = pdf_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
            return base64.b64encode(pix.tobytes("png")).decode("utf-8")

        container_l = ft.Container(content=None, padding=5)
        container_r = ft.Container(content=None, padding=5)

        spread_view = ft.Row(
            controls=[container_l, container_r], 
            spacing=2, 
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.CENTER
        )

        spread_container = ft.Container(content=spread_view, padding=0)

        scrollable_row = ft.Row([spread_container], scroll=ft.ScrollMode.ALWAYS, alignment=ft.MainAxisAlignment.CENTER)
        scrollable_col = ft.Column([scrollable_row], scroll=ft.ScrollMode.ALWAYS, expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER)

        last_rendered_page = -99
        last_mobile_state = is_mobile_screen()

        def render_spread(page_num):
            nonlocal last_rendered_page, last_mobile_state
            mobile_mode = is_mobile_screen()
            
            # បើប្តូររវាង Mobile និង Desktop ត្រូវរៀបចំក្បួនទំព័រឡើងវិញ
            if mobile_mode != last_mobile_state:
                last_mobile_state = mobile_mode
                if not mobile_mode and page_num % 2 != 0:
                    page_num -= 1

            if page_num != last_rendered_page or mobile_mode != last_mobile_state:
                try:
                    last_rendered_page = page_num
                    cached_img_left = get_page_image(page_num)
                    
                    if mobile_mode:
                        # បង្ហាញតែ ១ ទំព័រ ពេលនៅលើទូរសព្ទ
                        container_r.visible = False
                        if cached_img_left:
                            container_l.content = ft.Image(src_base64=cached_img_left, fit=ft.ImageFit.CONTAIN)
                            container_l.bgcolor = ft.colors.WHITE
                            container_l.shadow = ft.BoxShadow(blur_radius=8, color=ft.colors.BLACK26, offset=ft.Offset(0, 3))
                        else:
                            container_l.content = None
                            container_l.bgcolor = ft.colors.TRANSPARENT
                            container_l.shadow = None
                    else:
                        # បង្ហាញ ២ ទំព័រ ពេលនៅលើកុំព្យូទ័រ
                        container_r.visible = True
                        cached_img_right = get_page_image(page_num + 1)
                        
                        if cached_img_left:
                            container_l.content = ft.Image(src_base64=cached_img_left, fit=ft.ImageFit.CONTAIN)
                            container_l.bgcolor = ft.colors.WHITE
                            container_l.shadow = ft.BoxShadow(blur_radius=8, color=ft.colors.BLACK26, offset=ft.Offset(-3, 3))
                        else:
                            container_l.content = None
                            container_l.bgcolor = ft.colors.TRANSPARENT
                            container_l.shadow = None

                        if cached_img_right:
                            container_r.content = ft.Image(src_base64=cached_img_right, fit=ft.ImageFit.CONTAIN)
                            container_r.bgcolor = ft.colors.WHITE
                            container_r.shadow = ft.BoxShadow(blur_radius=8, color=ft.colors.BLACK26, offset=ft.Offset(3, 3))
                        else:
                            container_r.content = None
                            container_r.bgcolor = ft.colors.TRANSPARENT
                            container_r.shadow = None
                except Exception as e:
                    page_text.value = f"Error: {e}"
                    page.update()
                    return

            current_width = base_page_width * pdf_zoom
            if container_l.content: container_l.content.width = current_width
            if container_r.content and not mobile_mode: container_r.content.width = current_width
            
            book_width = current_width if mobile_mode else (current_width * 2 + 15)
            book_height = current_width * 1.414 + 15
            
            sc_width = page.width if page.width > 0 else 1100
            sc_height = page.height if page.height > 0 else 800
            
            left_p = max(0, (sc_width - 20 - book_width) / 2)
            top_p = max(0, (sc_height - 100 - book_height) / 2)
            
            spread_container.padding = ft.padding.only(left=left_p, right=left_p, top=top_p, bottom=top_p)
            
            if mobile_mode:
                page_text.value = f"ទំព័រ {page_num + 1}/{total_pages}"
            else:
                right_num = min(page_num + 2, total_pages)
                if page_num + 1 == right_num:
                    page_text.value = f"ទំព័រ {page_num + 1} នៃ {total_pages}"
                else:
                    page_text.value = f"ទំព័រ {page_num + 1}-{right_num} នៃ {total_pages}"
                
            save_progress(pdf_name, page_num)
            page.update()

        def on_resize(e):
            if page.current_view == "reader":
                render_spread(current_page)
        page.on_resize = on_resize

        def go_next(e):
            nonlocal current_page
            step = 1 if is_mobile_screen() else 2
            if current_page < total_pages - step:
                current_page += step
                render_spread(current_page)

        def go_prev(e):
            nonlocal current_page
            step = 1 if is_mobile_screen() else 2
            if current_page >= step:
                current_page -= step
                render_spread(current_page)
        
        def zoom_pdf_in(e):
            nonlocal pdf_zoom
            if pdf_zoom < 3.5: 
                pdf_zoom = round(pdf_zoom + 0.2, 1)
                zoom_text_display.value = f"{int(pdf_zoom * 100)}%"
                save_zoom(pdf_zoom)
                render_spread(current_page)
                
        def zoom_pdf_out(e):
            nonlocal pdf_zoom
            if pdf_zoom > 0.6: 
                pdf_zoom = round(pdf_zoom - 0.2, 1)
                zoom_text_display.value = f"{int(pdf_zoom * 100)}%"
                save_zoom(pdf_zoom)
                render_spread(current_page)

        btn_back = ft.IconButton(icon=ft.icons.ARROW_BACK, icon_size=20, tooltip="ត្រឡប់ក្រោយ", on_click=lambda e: show_library())
        btn_zoom_out = ft.IconButton(icon=ft.icons.ZOOM_OUT, icon_size=18, on_click=zoom_pdf_out)
        btn_zoom_in = ft.IconButton(icon=ft.icons.ZOOM_IN, icon_size=18, on_click=zoom_pdf_in)
        
        zoom_pdf_controls = ft.Row([btn_zoom_out, zoom_text_display, btn_zoom_in], spacing=0)

        btn_prev = ft.ElevatedButton("« មុន", on_click=go_prev)
        btn_next = ft.ElevatedButton("បន្ទាប់ »", on_click=go_next)

        page.controls.clear()
        page.add(
            ft.Column([
                ft.Row([
                    ft.Row([btn_back, zoom_pdf_controls], spacing=5), 
                    btn_prev, page_text, btn_next
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Container(height=5),
                scrollable_col
            ], expand=True)
        )
        render_spread(current_page)

    show_library()

ft.app(target=main)