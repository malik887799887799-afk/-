# -*- coding: utf-8 -*-
"""
برنامج مخزن Windows - واجهة عربية
يتصل بنفس Firebase Realtime Database الذي يستخدمه تطبيق Android:
storeData/products, storeData/people
يتطلب السماح الآمن بالوصول إلى قاعدة البيانات. لا تضع Database Secret داخل البرنامج.
"""
import json
import threading
import time
import urllib.request
import urllib.error
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from datetime import datetime

DATABASE_URL = "https://stor-f879a-default-rtdb.firebaseio.com/"
ROOT_PATH = "storeData"
POLL_SECONDS = 4

def firebase_request(path, method="GET", payload=None):
    url = DATABASE_URL.rstrip("/") + "/" + path.strip("/") + ".json"
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Firebase رفض الطلب ({e.code}): {detail}")
    except Exception as e:
        raise RuntimeError(str(e))

def money(value):
    try:
        n = float(value or 0)
        return f"{n:,.2f}".rstrip("0").rstrip(".")
    except Exception:
        return "0"

def now_text():
    return datetime.now().strftime("%Y/%m/%d %H:%M")

class StoreWindows:
    def __init__(self, root):
        self.root = root
        self.root.title("إدارة المخزن والديون")
        self.root.geometry("1050x680")
        self.root.minsize(850, 560)
        self.root.configure(bg="#f3f7fa")
        self.products = {}
        self.people = {}
        self.current_tab = "products"
        self.last_error = None
        self.loading = False
        self.build_ui()
        self.refresh_async()
        self.root.after(POLL_SECONDS * 1000, self.poll)

    def build_ui(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Treeview", rowheight=30, font=("Tahoma", 10))
        style.configure("Treeview.Heading", font=("Tahoma", 10, "bold"))
        style.configure("TButton", font=("Tahoma", 10), padding=6)
        style.configure("TNotebook.Tab", font=("Tahoma", 11, "bold"), padding=(18, 9))

        header = tk.Frame(self.root, bg="#19232d", height=65)
        header.pack(fill="x")
        tk.Label(header, text="إدارة المخزن والديون", bg="#19232d", fg="white",
                 font=("Tahoma", 18, "bold")).pack(side="right", padx=22, pady=14)
        self.connection = tk.Label(header, text="جارٍ الاتصال...", bg="#19232d", fg="#cde8d8",
                                   font=("Tahoma", 10))
        self.connection.pack(side="left", padx=20)

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=12)
        self.products_tab = tk.Frame(self.notebook, bg="#f3f7fa")
        self.people_tab = tk.Frame(self.notebook, bg="#f3f7fa")
        self.notebook.add(self.products_tab, text="المنتجات")
        self.notebook.add(self.people_tab, text="العملاء والموردون")
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        self.build_products_tab()
        self.build_people_tab()

        footer = tk.Frame(self.root, bg="#f3f7fa")
        footer.pack(fill="x", padx=12, pady=(0, 10))
        tk.Label(footer, text="التحديث تلقائي كل عدة ثوانٍ — يلزم اتصال بالإنترنت",
                 bg="#f3f7fa", fg="#66737e", font=("Tahoma", 9)).pack(side="right")
        ttk.Button(footer, text="تحديث الآن", command=self.refresh_async).pack(side="left")

    def build_products_tab(self):
        bar = tk.Frame(self.products_tab, bg="#f3f7fa")
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="إضافة منتج", command=self.add_product).pack(side="right", padx=4)
        ttk.Button(bar, text="تعديل المحدد", command=self.edit_product).pack(side="right", padx=4)
        ttk.Button(bar, text="حذف المحدد", command=self.delete_product).pack(side="right", padx=4)
        self.product_search = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.product_search, justify="right", width=30)
        ent.pack(side="left", padx=4)
        ent.bind("<KeyRelease>", lambda e: self.render_products())
        tk.Label(bar, text="بحث:", bg="#f3f7fa", font=("Tahoma", 10)).pack(side="left")

        cols = ("id", "name", "price", "stock")
        self.product_tree = ttk.Treeview(self.products_tab, columns=cols, show="headings")
        for col, label, width in [
            ("id", "رقم", 80), ("name", "اسم المنتج", 430),
            ("price", "السعر", 180), ("stock", "الكمية", 160)
        ]:
            self.product_tree.heading(col, text=label)
            self.product_tree.column(col, width=width, anchor="center")
        self.product_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.product_tree.bind("<Double-1>", lambda e: self.edit_product())

    def build_people_tab(self):
        bar = tk.Frame(self.people_tab, bg="#f3f7fa")
        bar.pack(fill="x", padx=8, pady=8)
        ttk.Button(bar, text="إضافة عميل", command=lambda: self.add_person(True)).pack(side="right", padx=4)
        ttk.Button(bar, text="إضافة مورد", command=lambda: self.add_person(False)).pack(side="right", padx=4)
        ttk.Button(bar, text="تسجيل حركة", command=self.add_transaction).pack(side="right", padx=4)
        ttk.Button(bar, text="عرض السجل", command=self.show_history).pack(side="right", padx=4)
        ttk.Button(bar, text="تعديل الاسم", command=self.edit_person).pack(side="right", padx=4)
        ttk.Button(bar, text="حذف الشخص", command=self.delete_person).pack(side="right", padx=4)
        self.people_search = tk.StringVar()
        ent = ttk.Entry(bar, textvariable=self.people_search, justify="right", width=25)
        ent.pack(side="left", padx=4)
        ent.bind("<KeyRelease>", lambda e: self.render_people())
        tk.Label(bar, text="بحث:", bg="#f3f7fa", font=("Tahoma", 10)).pack(side="left")

        cols = ("id", "kind", "name", "balance")
        self.people_tree = ttk.Treeview(self.people_tab, columns=cols, show="headings")
        for col, label, width in [
            ("id", "رقم", 80), ("kind", "النوع", 150),
            ("name", "الاسم", 440), ("balance", "الرصيد", 180)
        ]:
            self.people_tree.heading(col, text=label)
            self.people_tree.column(col, width=width, anchor="center")
        self.people_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.people_tree.bind("<Double-1>", lambda e: self.show_history())

    def on_tab_changed(self, _event=None):
        self.current_tab = "products" if self.notebook.index("current") == 0 else "people"

    def refresh_async(self):
        if self.loading:
            return
        self.loading = True
        threading.Thread(target=self._fetch_data, daemon=True).start()

    def _normalize_records(self, raw):
        # Firebase قد يعيد القائمة كـ [None, None, {سجل}, ...]
        # بدل قاموس، خصوصًا عندما تكون المفاتيح أرقامًا متباعدة.
        if isinstance(raw, dict):
            return {str(k): v for k, v in raw.items() if v is not None}
        if isinstance(raw, list):
            return {str(i): value for i, value in enumerate(raw) if value is not None}
        return {}

    def _fetch_data(self):
        try:
            products_raw = firebase_request(ROOT_PATH + "/products")
            people_raw = firebase_request(ROOT_PATH + "/people")
            products = self._normalize_records(products_raw)
            people = self._normalize_records(people_raw)
            self.root.after(0, lambda p=products, pe=people: self.apply_data(p, pe))
            self.root.after(0, lambda: self.set_connection(
                f"متصل — المنتجات: {len(products)} | الأشخاص: {len(people)}",
                "#a8e6c2"))
            self.last_error = None
        except Exception as e:
            msg = str(e)
            self.last_error = msg
            self.root.after(0, lambda m=msg: self.set_connection("تعذر الاتصال بقاعدة البيانات", "#ffb5b5"))
            self.root.after(0, lambda m=msg: self.maybe_show_error(m))
        finally:
            self.loading = False

    def maybe_show_error(self, msg):
        # لا نكرر نافذة الخطأ كل دورة؛ نعرضها مرة واحدة حتى يتغير الخطأ.
        if getattr(self, "_shown_error", None) != msg:
            self._shown_error = msg
            messagebox.showerror("مشكلة في Firebase", msg + "\n\nتأكد من عنوان قاعدة البيانات وقواعد الوصول.")

    def set_connection(self, text, color):
        self.connection.configure(text=text, fg=color)

    def apply_data(self, products, people):
        self.products = products if isinstance(products, dict) else {}
        self.people = people if isinstance(people, dict) else {}
        self.render_products()
        self.render_people()

    def poll(self):
        self.refresh_async()
        self.root.after(POLL_SECONDS * 1000, self.poll)

    def next_id(self, mapping):
        vals = []
        for key, value in (mapping or {}).items():
            if isinstance(value, dict):
                try: vals.append(int(value.get("id", key)))
                except Exception: pass
        return max(vals or [0]) + 1

    def selected_key(self, tree):
        selected = tree.selection()
        return selected[0] if selected else None

    def render_products(self):
        if not hasattr(self, "product_tree"): return
        for row in self.product_tree.get_children(): self.product_tree.delete(row)
        q = self.product_search.get().strip().casefold()
        def sort_key(pair):
            obj = pair[1] if isinstance(pair[1], dict) else {}
            return str(obj.get("name", "")).casefold()
        for key, p in sorted(self.products.items(), key=sort_key):
            if not isinstance(p, dict): continue
            name = str(p.get("name", ""))
            if q and q not in name.casefold(): continue
            self.product_tree.insert("", "end", iid=str(key),
                values=(p.get("id", key), name, money(p.get("price", 0)), money(p.get("stock", 0))))

    def render_people(self):
        if not hasattr(self, "people_tree"): return
        for row in self.people_tree.get_children(): self.people_tree.delete(row)
        q = self.people_search.get().strip().casefold()
        def sort_key(pair):
            obj = pair[1] if isinstance(pair[1], dict) else {}
            return str(obj.get("name", "")).casefold()
        for key, p in sorted(self.people.items(), key=sort_key):
            if not isinstance(p, dict): continue
            name = str(p.get("name", ""))
            if q and q not in name.casefold(): continue
            kind = "عميل" if p.get("isCustomer", True) else "مورد"
            try:
                bal = float(p.get("balance", 0) or 0)
            except (TypeError, ValueError):
                bal = 0.0
            self.people_tree.insert("", "end", iid=str(key),
                values=(p.get("id", key), kind, name, money(bal)))

    def write_async(self, path, method, payload=None, success_text="تم الحفظ"):
        def worker():
            try:
                firebase_request(ROOT_PATH + "/" + path, method, payload)
                self.root.after(0, lambda: self.set_connection(success_text, "#a8e6c2"))
                self.root.after(250, self.refresh_async)
            except Exception as e:
                self.root.after(0, lambda m=str(e): messagebox.showerror("فشل الحفظ", m))
        threading.Thread(target=worker, daemon=True).start()

    def add_product(self):
        name = simpledialog.askstring("إضافة منتج", "اسم المنتج:", parent=self.root)
        if name is None: return
        name = name.strip()
        if not name:
            messagebox.showwarning("تنبيه", "اكتب اسم المنتج.")
            return
        price = simpledialog.askfloat("إضافة منتج", "السعر:", minvalue=0, parent=self.root)
        if price is None: return
        stock = simpledialog.askfloat("إضافة منتج", "الكمية (يمكن أن تكون صفرًا):", minvalue=0, parent=self.root)
        if stock is None: stock = 0
        pid = self.next_id(self.products)
        product = {"id": pid, "name": name, "price": price, "stock": stock}
        self.write_async(f"products/{pid}", "PUT", product, "تمت إضافة المنتج")

    def edit_product(self):
        key = self.selected_key(self.product_tree)
        if key is None:
            messagebox.showinfo("اختيار", "اختار منتج الأول.")
            return
        p = self.products.get(key, {})
        name = simpledialog.askstring("تعديل منتج", "اسم المنتج:", initialvalue=p.get("name", ""), parent=self.root)
        if name is None: return
        price = simpledialog.askfloat("تعديل منتج", "السعر:", initialvalue=float(p.get("price", 0) or 0), minvalue=0, parent=self.root)
        if price is None: return
        stock = simpledialog.askfloat("تعديل منتج", "الكمية:", initialvalue=float(p.get("stock", 0) or 0), minvalue=0, parent=self.root)
        if stock is None: return
        updated = dict(p, id=int(p.get("id", key)), name=name.strip(), price=price, stock=stock)
        self.write_async(f"products/{key}", "PUT", updated, "تم تعديل المنتج")

    def delete_product(self):
        key = self.selected_key(self.product_tree)
        if key is None: return messagebox.showinfo("اختيار", "اختار منتج الأول.")
        p = self.products.get(key, {})
        if messagebox.askyesno("تأكيد الحذف", f"تحذف المنتج «{p.get('name','')}»؟"):
            self.write_async(f"products/{key}", "DELETE", None, "تم حذف المنتج")

    def add_person(self, is_customer):
        name = simpledialog.askstring("إضافة شخص", "الاسم:", parent=self.root)
        if name is None: return
        name = name.strip()
        if not name: return messagebox.showwarning("تنبيه", "اكتب الاسم.")
        pid = self.next_id(self.people)
        person = {"id": pid, "name": name, "isCustomer": bool(is_customer), "balance": 0, "history": {}}
        self.write_async(f"people/{pid}", "PUT", person, "تمت إضافة الشخص")

    def edit_person(self):
        key = self.selected_key(self.people_tree)
        if key is None: return messagebox.showinfo("اختيار", "اختار عميل أو مورد الأول.")
        p = self.people.get(key, {})
        name = simpledialog.askstring("تعديل الاسم", "الاسم:", initialvalue=p.get("name", ""), parent=self.root)
        if name is None or not name.strip(): return
        updated = dict(p, name=name.strip())
        self.write_async(f"people/{key}", "PUT", updated, "تم تعديل الاسم")

    def delete_person(self):
        key = self.selected_key(self.people_tree)
        if key is None: return messagebox.showinfo("اختيار", "اختار عميل أو مورد الأول.")
        p = self.people.get(key, {})
        if messagebox.askyesno("تأكيد الحذف", f"تحذف «{p.get('name','')}» وسجل حركاته؟"):
            self.write_async(f"people/{key}", "DELETE", None, "تم حذف الشخص")

    def add_transaction(self):
        key = self.selected_key(self.people_tree)
        if key is None: return messagebox.showinfo("اختيار", "اختار عميل أو مورد الأول.")
        p = self.people.get(key, {})
        typ = simpledialog.askstring("تسجيل حركة", "نوع الحركة كما يستخدمه التطبيق (مثال: أخذ أو أعطى):", initialvalue="أخذ", parent=self.root)
        if typ is None or not typ.strip(): return
        amount = simpledialog.askfloat("تسجيل حركة", "المبلغ:", minvalue=0.01, parent=self.root)
        if amount is None: return
        note = simpledialog.askstring("تسجيل حركة", "التفاصيل:", parent=self.root)
        if note is None: note = ""
        history = p.get("history") if isinstance(p.get("history"), dict) else {}
        tid = self.next_id(history)
        trans = {"id": tid, "type": typ.strip(), "amount": amount, "note": note.strip(), "date": now_text()}
        new_history = dict(history)
        new_history[str(tid)] = trans
        # Android model derives balance from history; don't trust or manually set a separate balance.
        updated = dict(p, history=new_history)
        balance = 0.0
        for t in new_history.values():
            if isinstance(t, dict):
                amt = float(t.get("amount", 0) or 0)
                balance += amt if t.get("type") == "أخذ" else -amt
        updated["balance"] = balance
        self.write_async(f"people/{key}", "PUT", updated, "تم تسجيل الحركة")

    def show_history(self):
        key = self.selected_key(self.people_tree)
        if key is None: return messagebox.showinfo("اختيار", "اختار عميل أو مورد الأول.")
        p = self.people.get(key, {})
        win = tk.Toplevel(self.root)
        win.title("سجل الحركات - " + str(p.get("name", "")))
        win.geometry("700x420")
        cols = ("date", "type", "note", "amount")
        tree = ttk.Treeview(win, columns=cols, show="headings")
        for c, label, width in [("date","التاريخ",150),("type","الحركة",100),("note","التفاصيل",300),("amount","المبلغ",120)]:
            tree.heading(c, text=label); tree.column(c, width=width, anchor="center")
        tree.pack(fill="both", expand=True, padx=10, pady=10)
        history = p.get("history") if isinstance(p.get("history"), dict) else {}
        entries = sorted(history.items(), key=lambda kv: str((kv[1] or {}).get("date", "")), reverse=True)
        for tid, t in entries:
            if isinstance(t, dict):
                tree.insert("", "end", iid=str(tid), values=(t.get("date",""), t.get("type",""), t.get("note",""), money(t.get("amount",0))))
        ttk.Button(win, text="إغلاق", command=win.destroy).pack(pady=(0,10))

if __name__ == "__main__":
    root = tk.Tk()
    app = StoreWindows(root)
    root.mainloop()
