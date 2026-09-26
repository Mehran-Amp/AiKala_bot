import React from "react";
import { ReceiptData } from "../types";
import { Printer, CheckCircle2, Clock, MapPin, Phone, Building2, ShieldCheck, QrCode } from "lucide-react";

interface OptionBReceiptProps {
  data: ReceiptData;
  onPrint?: () => void;
}

export const OptionBReceipt: React.FC<OptionBReceiptProps> = ({ data, onPrint }) => {
  const formatPrice = (val: number) => {
    return val.toLocaleString("fa-IR");
  };

  return (
    <div className="flex flex-col items-center">
      {/* Action Bar */}
      <div className="w-full max-w-[440px] flex items-center justify-between mb-3 px-2">
        <div className="flex items-center gap-1.5 text-xs text-slate-300">
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse"></span>
          <span className="font-semibold text-emerald-400">طراحی استاندارد Option B (فیش پرینتر ۸۰mm)</span>
        </div>
        {onPrint && (
          <button
            onClick={onPrint}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-100 rounded-lg text-xs font-semibold border border-slate-700 transition shadow-sm cursor-pointer"
          >
            <Printer className="w-3.5 h-3.5 text-rose-400" />
            چاپ / ذخیره فیش
          </button>
        )}
      </div>

      {/* 80mm Thermal Receipt Container - Option B Exact Design */}
      <div
        id="printable-receipt-option-b"
        className="w-full max-w-[440px] bg-white text-slate-900 shadow-2xl rounded-2xl p-6 border border-slate-200 font-sans relative overflow-hidden text-right leading-relaxed"
      >
        {/* Receipt Header Paper Line */}
        <div className="absolute top-0 left-0 right-0 h-1.5 bg-gradient-to-r from-rose-500 via-amber-500 to-indigo-600" />

        {/* 1. Shop Header */}
        <div className="text-center pb-4 border-b border-dashed border-slate-300">
          <div className="flex items-center justify-center gap-1.5 text-slate-900 mb-1">
            <Building2 className="w-5 h-5 text-rose-600" />
            <h1 className="text-xl font-black tracking-tight">{data.shopName}</h1>
          </div>

          {/* Option B Badge: Pre-Invoice vs Final Invoice */}
          <div className="my-2 inline-block">
            {data.isPreInvoice ? (
              <div className="bg-amber-50 text-amber-900 border border-amber-300 px-3.5 py-1 rounded-full text-xs font-black inline-flex items-center gap-1.5 shadow-xs">
                <Clock className="w-3.5 h-3.5 text-amber-700" />
                <span>پـیـش‌فـاکـتـور رسـمـی خـریـد (غـیـرقـطـعـی)</span>
              </div>
            ) : (
              <div className="bg-emerald-50 text-emerald-900 border border-emerald-300 px-3.5 py-1 rounded-full text-xs font-black inline-flex items-center gap-1.5 shadow-xs">
                <CheckCircle2 className="w-3.5 h-3.5 text-emerald-700" />
                <span>فـاکـتـور فـروش رسـمـی و قـطـعـی</span>
              </div>
            )}
          </div>

          <div className="text-[11px] text-slate-500 space-y-0.5 mt-1 leading-normal">
            <p className="flex items-center justify-center gap-1">
              <MapPin className="w-3 h-3 text-slate-400 shrink-0" />
              <span>{data.shopAddress}</span>
            </p>
            <p className="flex items-center justify-center gap-1">
              <Phone className="w-3 h-3 text-slate-400 shrink-0" />
              <span>تلفن: {data.shopPhone} | شماره جواز / ثبت: {data.licenseNo}</span>
            </p>
          </div>
        </div>

        {/* 2. Order & Customer Info (Option B Layout) */}
        <div className="py-3.5 border-b border-dashed border-slate-300 text-xs space-y-1.5">
          <div className="flex justify-between items-center">
            <span className="text-slate-500">شماره سند:</span>
            <span className="font-semibold text-slate-800">{data.invoiceNumber}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-500">کد رهگیری سفارش:</span>
            <span className="font-black text-rose-600 tracking-wider text-sm">#{data.orderCode}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-500">تاریخ و ساعت صدور:</span>
            <span className="font-medium text-slate-700">{data.date}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-500">نام تحویل‌گیرنده:</span>
            <span className="font-bold text-slate-900">{data.customerName}</span>
          </div>
          <div className="flex justify-between items-center">
            <span className="text-slate-500">شماره تماس همراه:</span>
            <span className="font-semibold text-slate-800 dir-ltr">{data.customerPhone}</span>
          </div>
          {data.customerPostal && (
            <div className="flex justify-between items-center">
              <span className="text-slate-500">کد پستی:</span>
              <span className="font-medium text-slate-700">{data.customerPostal}</span>
            </div>
          )}
          <div className="pt-1.5 text-[11px] text-slate-700 leading-relaxed bg-slate-50 p-2.5 rounded-lg border border-slate-200">
            <span className="font-bold text-slate-800">نشانی مقصد: </span>
            <span>{data.customerAddress}</span>
          </div>
        </div>

        {/* 3. Items List (Option B Single-Column Thermal Design) */}
        <div className="py-3.5 border-b border-dashed border-slate-300">
          <div className="flex justify-between text-[11px] font-bold text-slate-500 uppercase tracking-wider mb-2 pb-1 border-b border-slate-200">
            <span>شرح کالا و مشخصات فنی</span>
            <span>مبلغ (تومان)</span>
          </div>
          <div className="space-y-2.5">
            {data.items.map((item, idx) => (
              <div key={idx} className="text-xs">
                <div className="flex justify-between items-start gap-2">
                  <span className="font-bold text-slate-900 leading-snug">{item.name}</span>
                  <span className="font-black text-slate-900 shrink-0 text-left">
                    {formatPrice(item.total)}
                  </span>
                </div>
                {item.meta && (
                  <p className="text-[11px] text-slate-500 mt-0.5 leading-relaxed">
                    • {item.meta}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* 4. Financial Calculations & Deposit Status (Option B Rules) */}
        <div className="py-3.5 border-b border-dashed border-slate-300 space-y-2 text-xs">
          <div className="flex justify-between items-center">
            <span className="text-slate-600 font-medium">مبلغ کل کالا:</span>
            <span className="font-bold text-slate-900 text-sm">{formatPrice(data.grandTotal)} تومان</span>
          </div>

          {/* Deposit Row */}
          <div className="flex justify-between items-center py-1.5 px-2.5 rounded-lg bg-slate-50 border border-slate-200">
            <span className="font-medium text-slate-700">مبلغ بیعانه پیش‌پرداخت (۸٪):</span>
            <div className="text-left flex items-center gap-1.5">
              <span className="font-bold text-slate-900">{formatPrice(data.deposit)} تومان</span>
              {data.isPreInvoice ? (
                <span className="text-[10px] bg-amber-200/90 text-amber-950 font-bold px-2 py-0.5 rounded">
                  در انتظار واریز ⏳
                </span>
              ) : (
                <span className="text-[10px] bg-emerald-200/90 text-emerald-950 font-bold px-2 py-0.5 rounded flex items-center gap-0.5">
                  <CheckCircle2 className="w-2.5 h-2.5 inline" /> پرداخت شد
                </span>
              )}
            </div>
          </div>

          {/* Remaining Balance Box */}
          <div className="p-3 rounded-xl bg-rose-50 border border-rose-200 flex justify-between items-center">
            <div className="text-right">
              <span className="block font-bold text-rose-950 text-xs">مانده تسویه در محل:</span>
              <span className="text-[10px] text-rose-700 font-medium">پس از تحویل، بررسی اصالت و تست کامل</span>
            </div>
            <span className="font-black text-rose-700 text-base tracking-tight">
              {formatPrice(data.remaining)} تومان
            </span>
          </div>

          {data.isPreInvoice && (
            <div className="bg-amber-50 border border-amber-200 rounded-lg p-2 text-[11px] text-amber-900 flex items-start gap-1.5">
              <Clock className="w-3.5 h-3.5 text-amber-700 shrink-0 mt-0.5" />
              <span>
                توجه: این پیش‌فاکتور به مدت ۳ ساعت معتبر است. پس از واریز بیعانه و تایید، فاکتور قطعی صادر می‌گردد.
              </span>
            </div>
          )}
        </div>

        {/* 5. Terms & Guarantees */}
        <div className="py-3.5 border-b border-dashed border-slate-300 text-[10px] text-slate-600 space-y-1.5 leading-relaxed">
          <div className="flex items-center gap-1 font-bold text-slate-800 text-[11px] mb-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>شرایط فروش، تحویل و گارانتی کالا:</span>
          </div>
          <p>۱. گارانتی کتبی: کلیه اجناس دارای ۲ سال ضمانت تعویض قطعات و ۵ سال خدمات پس از فروش سراسری می‌باشند.</p>
          <p>۲. مهلت تست: خریدار موظف است کالا را هنگام تحویل از لحاظ اصالت و سلامت ظاهری و روشن شدن تست نماید.</p>
          <p>۳. تسویه نهایی: مانده حساب فاکتور پس از تحویل و رضایت در محل توسط خریدار تسویه می‌گردد.</p>
        </div>

        {/* 6. Seal & QR Code */}
        <div className="pt-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-14 h-14 bg-slate-900 rounded-lg flex items-center justify-center text-white shadow-xs">
              <QrCode className="w-10 h-10" />
            </div>
            <div className="text-[10px] text-slate-500 leading-tight">
              <span className="font-bold text-slate-700 block">رهگیری آنلاین</span>
              <span>AiKala_bot@</span>
            </div>
          </div>

          <div className="relative">
            <div
              className={`w-32 h-14 rounded-full border-2 border-dashed flex flex-col items-center justify-center p-1 transform -rotate-3 ${
                data.isPreInvoice
                  ? "border-amber-500 bg-amber-50/60 text-amber-900"
                  : "border-emerald-600 bg-emerald-50/60 text-emerald-900"
              }`}
            >
              <span className="text-[10px] font-black">{data.shopName}</span>
              <span className="text-[9px] font-bold mt-0.5">
                {data.isPreInvoice ? "پیش‌فاکتور - در انتظار واریز" : "مهر تایید مالی - صادر شد"}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-4 pt-2 text-center text-[10px] text-slate-400 border-t border-slate-100">
          فروشگاه لوازم خانگی آی‌کالا • ارسال مطمئن با باربری اختصاصی به سراسر کشور
        </div>
      </div>
    </div>
  );
};
