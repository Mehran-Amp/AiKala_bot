import React, { useState } from "react";
import { Radio, Plus, Trash2, RefreshCw, CheckCircle, AlertTriangle, ShieldCheck, Eye } from "lucide-react";

interface MonitoredChannel {
  id: string;
  username: string;
  name: string;
  status: "active" | "syncing" | "paused";
  lastPostTime: string;
  postCount: number;
}

export const ChannelMonitorTab: React.FC = () => {
  const [channels, setChannels] = useState<MonitoredChannel[]>([
    {
      id: "1",
      username: "@Aikala_Image",
      name: "گالری مرکزی تصاویر آی‌کالا",
      status: "active",
      lastPostTime: "۱۰ دقیقه پیش",
      postCount: 68
    },
    {
      id: "2",
      username: "@LG_SAMSUNG_DEAWOO",
      name: "کانال اصلی واردات و قیمت فقیه‌زاده",
      status: "active",
      lastPostTime: "۲۵ دقیقه پیش",
      postCount: 142
    }
  ]);

  const [newChannelInput, setNewChannelInput] = useState("");
  const [syncing, setSyncing] = useState(false);

  const handleAddChannel = () => {
    if (!newChannelInput.trim()) return;
    const cleanUsername = newChannelInput.startsWith("@") ? newChannelInput.trim() : `@${newChannelInput.trim()}`;
    const newChan: MonitoredChannel = {
      id: Date.now().toString(),
      username: cleanUsername,
      name: `کانال همکار (${cleanUsername})`,
      status: "active",
      lastPostTime: "اکنون",
      postCount: 0
    };
    setChannels([...channels, newChan]);
    setNewChannelInput("");
  };

  const handleDeleteChannel = (id: string) => {
    setChannels(channels.filter(c => c.id !== id));
  };

  const handleManualSync = () => {
    setSyncing(true);
    setTimeout(() => {
      setSyncing(false);
    }, 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header Info */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="p-2 rounded-xl bg-indigo-500/10 text-indigo-400 border border-indigo-500/20">
                <Radio className="w-5 h-5" />
              </span>
              <h2 className="text-lg font-black text-white">سامانه پایش هوشمند کانال‌های همکار و بازرگانی</h2>
            </div>
            <p className="text-xs text-slate-400 mt-1">
              تمام پست‌ها، تصاویر و آلبوم‌های منتشر شده در کانال‌های زیر به صورت لحظه‌ای با هوش مصنوعی دیپ‌سیک تحلیل و در گالری ثبت می‌شوند.
            </p>
          </div>

          <button
            onClick={handleManualSync}
            disabled={syncing}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-bold text-xs transition shadow-lg shadow-indigo-600/20 cursor-pointer disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
            {syncing ? "در حال همگام‌سازی..." : "همگام‌سازی فوری گالری"}
          </button>
        </div>
      </div>

      {/* Add New Channel Card */}
      <div className="bg-slate-900/90 border border-slate-800 rounded-2xl p-6">
        <h3 className="text-sm font-bold text-white mb-3 flex items-center gap-2">
          <Plus className="w-4 h-4 text-emerald-400" />
          افزودن کانال جدید به لیست پایش
        </h3>
        <div className="flex flex-col sm:flex-row gap-3">
          <input
            type="text"
            placeholder="آیدی کانال تلگرام (مثال: @faghihzadeh_kala)..."
            value={newChannelInput}
            onChange={(e) => setNewChannelInput(e.target.value)}
            className="flex-1 bg-slate-950 border border-slate-700/80 rounded-xl px-4 py-2.5 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
          />
          <button
            onClick={handleAddChannel}
            className="px-5 py-2.5 bg-emerald-600 hover:bg-emerald-500 text-white font-bold text-xs rounded-xl transition shadow-lg shadow-emerald-600/20 cursor-pointer flex items-center justify-center gap-2"
          >
            <Plus className="w-4 h-4" />
            افزودن به پایش
          </button>
        </div>
      </div>

      {/* Channels List */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {channels.map((chan) => (
          <div
            key={chan.id}
            className="bg-slate-900/80 border border-slate-800 rounded-2xl p-5 flex flex-col justify-between gap-4 hover:border-slate-700 transition"
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
                  <span className="font-black text-sm text-white">{chan.name}</span>
                </div>
                <p className="text-xs text-indigo-400 font-mono mt-1 direction-ltr text-right">{chan.username}</p>
              </div>

              <button
                onClick={() => handleDeleteChannel(chan.id)}
                className="p-2 text-slate-500 hover:text-rose-400 hover:bg-rose-500/10 rounded-lg transition"
                title="حذف از پایش"
              >
                <Trash2 className="w-4 h-4" />
              </button>
            </div>

            <div className="grid grid-cols-2 gap-2 pt-3 border-t border-slate-800/80 text-xs">
              <div className="bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/50">
                <span className="text-slate-500 block text-[10px]">تعداد آلبوم/عکس:</span>
                <span className="font-bold text-white text-sm">{chan.postCount} پست</span>
              </div>
              <div className="bg-slate-950/60 p-2.5 rounded-xl border border-slate-800/50">
                <span className="text-slate-500 block text-[10px]">آخرین بررسی:</span>
                <span className="font-bold text-slate-300">{chan.lastPostTime}</span>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
