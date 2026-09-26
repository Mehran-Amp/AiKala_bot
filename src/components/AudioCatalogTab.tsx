import React, { useState, useMemo } from "react";
import audioDataRaw from "../audio_catalog_data.json";
import {
  Volume2,
  Search,
  Sparkles,
  ShieldCheck,
  Zap,
  Sliders,
  FileSpreadsheet,
  Download,
  Tag,
  Radio,
  Music,
  CheckCircle2,
  Tv,
  Wind,
  Refrigerator,
  Laptop,
  Flame,
  Award
} from "lucide-react";

interface AudioItem {
  code: string;
  brand: string;
  model: string;
  sub: string;
  power: string;
  features: string;
  price: number;
}

export function AudioCatalogTab() {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedBrand, setSelectedBrand] = useState("all");
  const [selectedSub, setSelectedSub] = useState("all");
  const [sortBy, setSortBy] = useState<"price-desc" | "price-asc" | "code">("price-desc");
  const [viewMode, setViewMode] = useState<"table" | "cards">("table");

  const items = audioDataRaw as AudioItem[];

  // Brand counts
  const brands = useMemo(() => {
    const map = new Map<string, number>();
    items.forEach((it) => {
      const b = it.brand || "Other";
      map.set(b, (map.get(b) || 0) + 1);
    });
    return Array.from(map.entries());
  }, [items]);

  // Subcategory counts
  const subcategories = useMemo(() => {
    const map = new Map<string, number>();
    items.forEach((it) => {
      const s = it.sub || "سایر";
      map.set(s, (map.get(s) || 0) + 1);
    });
    return Array.from(map.entries());
  }, [items]);

  // Filtered & Sorted items
  const filteredItems = useMemo(() => {
    return items
      .filter((it) => {
        if (selectedBrand !== "all" && it.brand.toLowerCase() !== selectedBrand.toLowerCase()) {
          return false;
        }
        if (selectedSub !== "all" && it.sub !== selectedSub) {
          return false;
        }
        if (searchTerm.trim()) {
          const q = searchTerm.toLowerCase().trim();
          const matchName = it.model.toLowerCase().includes(q);
          const matchCode = it.code.toLowerCase().includes(q);
          const matchBrand = it.brand.toLowerCase().includes(q);
          const matchSub = it.sub.toLowerCase().includes(q);
          const matchFeat = it.features.toLowerCase().includes(q);
          if (!matchName && !matchCode && !matchBrand && !matchSub && !matchFeat) {
            return false;
          }
        }
        return true;
      })
      .sort((a, b) => {
        if (sortBy === "price-desc") return b.price - a.price;
        if (sortBy === "price-asc") return a.price - b.price;
        return a.code.localeCompare(b.code);
      });
  }, [items, selectedBrand, selectedSub, searchTerm, sortBy]);

  const formatToman = (val: number) => {
    return val.toLocaleString("fa-IR") + " تومان";
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Top Banner & Quick Context */}
      <div className="bg-gradient-to-r from-slate-900 via-indigo-950/80 to-slate-900 border border-indigo-500/20 rounded-2xl p-6 shadow-xl relative overflow-hidden">
        <div className="absolute -left-12 -top-12 w-48 h-48 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -right-12 -bottom-12 w-48 h-48 bg-rose-500/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="p-2 rounded-xl bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
                <Volume2 className="w-6 h-6" />
              </span>
              <h1 className="text-xl sm:text-2xl font-black text-white">
                کاتالوگ و لیست قیمت سیستم‌های صوتی و پارتی‌باکس
              </h1>
              <span className="text-xs bg-emerald-500/20 text-emerald-300 font-bold px-2.5 py-1 rounded-full border border-emerald-500/30">
                فعال در ربات AiKala_bot
              </span>
            </div>
            <p className="text-sm text-slate-300 max-w-3xl leading-relaxed">
              محصولات اورجینال صوتی از برندهای رسمی <strong className="text-indigo-300">JBL</strong>،{" "}
              <strong className="text-amber-300">Harman Kardon</strong> و{" "}
              <strong className="text-rose-300">Hopestar</strong> با استخراج توان، کدهای کاتالوگ و صدور استاندارد PDF.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="bg-slate-800/90 border border-slate-700/80 rounded-xl px-4 py-2.5 text-center">
              <span className="block text-xs text-slate-400 font-medium">کل مدل‌ها</span>
              <span className="text-lg font-black text-white">{items.length} دستگاه</span>
            </div>
            <div className="bg-slate-800/90 border border-slate-700/80 rounded-xl px-4 py-2.5 text-center">
              <span className="block text-xs text-slate-400 font-medium">ضمانت</span>
              <span className="text-sm font-black text-emerald-400 flex items-center gap-1">
                <ShieldCheck className="w-4 h-4 inline" /> ۱۰۰٪ اورجینال
              </span>
            </div>
          </div>
        </div>

        {/* Categories Bar */}
        <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center gap-2 overflow-x-auto text-xs pb-1">
          <span className="text-slate-400 shrink-0 font-bold flex items-center gap-1">
            سایر دسته‌های کاتالوگ فروشگاه:
          </span>
          <span className="bg-slate-800 text-slate-300 px-2.5 py-1 rounded-lg border border-slate-700/60 flex items-center gap-1">
            <Tv className="w-3.5 h-3.5 text-sky-400" /> تلویزیون
          </span>
          <span className="bg-slate-800 text-slate-300 px-2.5 py-1 rounded-lg border border-slate-700/60 flex items-center gap-1">
            <Wind className="w-3.5 h-3.5 text-cyan-400" /> کولر گازی
          </span>
          <span className="bg-slate-800 text-slate-300 px-2.5 py-1 rounded-lg border border-slate-700/60 flex items-center gap-1">
            <Refrigerator className="w-3.5 h-3.5 text-blue-400" /> یخچال فریزر
          </span>
          <span className="bg-slate-800 text-slate-300 px-2.5 py-1 rounded-lg border border-slate-700/60 flex items-center gap-1">
            <Laptop className="w-3.5 h-3.5 text-purple-400" /> لپ‌تاپ
          </span>
          <span className="bg-slate-800 text-slate-300 px-2.5 py-1 rounded-lg border border-slate-700/60 flex items-center gap-1">
            <Award className="w-3.5 h-3.5 text-amber-400" /> آاگ و میله
          </span>
          <span className="bg-indigo-600/30 text-indigo-200 px-2.5 py-1 rounded-lg border border-indigo-500/40 flex items-center gap-1 font-bold">
            <Volume2 className="w-3.5 h-3.5 text-indigo-400" /> سیستم صوتی (انتخاب شده)
          </span>
        </div>
      </div>

      {/* Controls & Filters Bar */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-4 sm:p-5 shadow-lg space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
          {/* Search box */}
          <div className="md:col-span-5 relative">
            <Search className="w-4 h-4 text-slate-400 absolute right-3.5 top-3 pointer-events-none" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="جستجو بر اساس مدل (PARTYBOX)، کد انبار (JB01)، توان یا قابلیت..."
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl pr-10 pl-4 py-2.5 text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-indigo-500 transition"
            />
            {searchTerm && (
              <button
                onClick={() => setSearchTerm("")}
                className="absolute left-3 top-2.5 text-xs text-slate-400 hover:text-white"
              >
                پاک کردن
              </button>
            )}
          </div>

          {/* Brand select */}
          <div className="md:col-span-3">
            <select
              value={selectedBrand}
              onChange={(e) => setSelectedBrand(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="all">همه برندها ({items.length})</option>
              {brands.map(([b, count], bIdx) => (
                <option key={`brand-${b}-${bIdx}`} value={b}>
                  {b} ({count} مدل)
                </option>
              ))}
            </select>
          </div>

          {/* Subcategory select */}
          <div className="md:col-span-2">
            <select
              value={selectedSub}
              onChange={(e) => setSelectedSub(e.target.value)}
              className="w-full bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2.5 text-sm text-slate-200 focus:outline-none focus:border-indigo-500"
            >
              <option value="all">همه نوع‌ها</option>
              {subcategories.map(([s, count], sIdx) => (
                <option key={`sub-${s}-${sIdx}`} value={s}>
                  {s} ({count})
                </option>
              ))}
            </select>
          </div>

          {/* Sort order & View toggle */}
          <div className="md:col-span-2 flex items-center justify-end gap-2">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
              className="bg-slate-950/80 border border-slate-800 rounded-xl px-3 py-2.5 text-xs text-slate-300 focus:outline-none"
            >
              <option value="price-desc">گران‌ترین</option>
              <option value="price-asc">ارزان‌ترین</option>
              <option value="code">کد کالا</option>
            </select>

            <div className="flex items-center bg-slate-950 border border-slate-800 rounded-xl p-1 text-xs">
              <button
                onClick={() => setViewMode("table")}
                className={`px-2.5 py-1.5 rounded-lg transition font-medium cursor-pointer ${
                  viewMode === "table" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
                }`}
                title="قالب استاندارد ۶ ستونه PDF"
              >
                جدول
              </button>
              <button
                onClick={() => setViewMode("cards")}
                className={`px-2.5 py-1.5 rounded-lg transition font-medium cursor-pointer ${
                  viewMode === "cards" ? "bg-indigo-600 text-white" : "text-slate-400 hover:text-white"
                }`}
                title="کارت‌های مشخصات"
              >
                کارت‌ها
              </button>
            </div>
          </div>
        </div>

        {/* Quick status bar */}
        <div className="flex items-center justify-between text-xs text-slate-400 border-t border-slate-800/80 pt-3">
          <div className="flex items-center gap-2">
            <span>نمایش:</span>
            <strong className="text-white font-bold">{filteredItems.length} کالا</strong>
            {searchTerm && <span>(فیلتر شده بر اساس «{searchTerm}»)</span>}
          </div>
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 flex items-center gap-1 font-medium">
              <CheckCircle2 className="w-3.5 h-3.5" /> موتور جستجو و تلگرام همگام هستند
            </span>
          </div>
        </div>
      </div>

      {/* Main Content Area */}
      {viewMode === "table" ? (
        /* Standard 6-Column PDF-Ready Table */
        <div className="bg-slate-900/90 border border-slate-800 rounded-2xl overflow-hidden shadow-xl">
          <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
            <div>
              <h2 className="text-sm font-bold text-slate-200">
                قالب استاندارد ۶ ستونه لیست قیمت (طراحی هماهنگ با خروجی PDF)
              </h2>
              <p className="text-xs text-slate-400 mt-0.5">
                شامل ردیف، مدل و نام دستگاه، برند سازنده، مشخصات و توان خروجی، کد انبار و قیمت نهایی
              </p>
            </div>
            <span className="text-xs px-2.5 py-1 rounded-lg bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 font-mono">
              ISO 32000-1 Pure Python Engine
            </span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead className="bg-slate-950/80 text-xs font-bold text-slate-400 border-b border-slate-800">
                <tr>
                  <th className="py-3 px-4 w-12 text-center">#</th>
                  <th className="py-3 px-4">مدل و نام دستگاه</th>
                  <th className="py-3 px-4 w-32 text-center">برند</th>
                  <th className="py-3 px-4">دسته‌بندی و توان خروجی</th>
                  <th className="py-3 px-4 w-28 text-center font-mono">کد کالا</th>
                  <th className="py-3 px-4 text-left w-44">قیمت (تومان)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredItems.map((item, idx) => (
                  <tr
                    key={item.code ? `row-${item.code}-${idx}` : `row-${idx}`}
                    className="hover:bg-slate-800/40 transition group font-medium"
                  >
                    <td className="py-3 px-4 text-center text-xs text-slate-500 font-mono">
                      {idx + 1}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-bold text-slate-100 group-hover:text-indigo-300 transition">
                        {item.model}
                      </div>
                      <div className="text-xs text-slate-400 line-clamp-1 mt-0.5">
                        {item.features}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className="px-2.5 py-1 rounded-lg bg-slate-800 text-slate-200 text-xs border border-slate-700/60 font-bold">
                        {item.brand}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="text-xs text-slate-300 font-medium">{item.sub}</div>
                      {item.power && (
                        <div className="text-[11px] text-amber-400 font-mono mt-0.5">
                          ⚡ توان: {item.power}
                        </div>
                      )}
                    </td>
                    <td className="py-3 px-4 text-center">
                      <span className="px-2 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20 text-xs font-mono font-bold">
                        {item.code}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-left font-mono font-bold text-emerald-400 text-base">
                      {formatToman(item.price)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* Cards View */
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {filteredItems.map((item, idx) => (
            <div
              key={item.code ? `card-${item.code}-${idx}` : `card-${idx}`}
              className="bg-slate-900/90 border border-slate-800 rounded-2xl p-5 shadow-lg flex flex-col justify-between hover:border-indigo-500/40 transition space-y-4 group"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="px-2.5 py-1 rounded-lg bg-indigo-500/20 text-indigo-300 text-xs font-bold border border-indigo-500/30">
                    {item.brand}
                  </span>
                  <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 text-xs font-mono font-bold border border-slate-700">
                    کد: {item.code}
                  </span>
                </div>

                <div>
                  <h3 className="text-base font-bold text-white group-hover:text-indigo-300 transition">
                    {item.model}
                  </h3>
                  <p className="text-xs text-slate-400 mt-1">{item.sub}</p>
                </div>

                {item.power && (
                  <div className="bg-slate-950/60 border border-slate-800/80 rounded-xl px-3 py-2 flex items-center justify-between text-xs">
                    <span className="text-slate-400 flex items-center gap-1">
                      <Zap className="w-3.5 h-3.5 text-amber-400" /> توان خروجی:
                    </span>
                    <span className="text-amber-300 font-mono font-bold">{item.power}</span>
                  </div>
                )}

                <div className="text-xs text-slate-400 line-clamp-2 leading-relaxed bg-slate-950/40 p-2.5 rounded-xl border border-slate-800/60">
                  {item.features}
                </div>
              </div>

              <div className="border-t border-slate-800/80 pt-3 flex items-center justify-between">
                <div className="text-xs text-slate-400">قیمت فروش:</div>
                <div className="text-base font-black text-emerald-400 font-mono">
                  {formatToman(item.price)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
