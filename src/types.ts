export interface OrderItem {
  name: string;
  meta?: string;
  code?: string;
  qty: number;
  unitPrice: number;
  total: number;
}

export interface ReceiptData {
  shopName: string;
  shopPhone: string;
  shopAddress: string;
  licenseNo: string;
  invoiceNumber: string;
  orderCode: string;
  date: string;
  customerName: string;
  customerPhone: string;
  customerPhone2?: string;
  customerAddress: string;
  customerPostal?: string;
  items: OrderItem[];
  subtotal: number;
  grandTotal: number;
  deposit: number;
  remaining: number;
  isPreInvoice: boolean; // true = پیش‌فاکتور (در انتظار واریز بیعانه), false = فاکتور فروش قطعی
}
