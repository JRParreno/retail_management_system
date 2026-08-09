import { ShopProvider } from "@/components/shop/shop-context";
import { Toaster } from "@/components/ui/sonner";

export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <ShopProvider>
      {children}
      <Toaster richColors position="top-center" />
    </ShopProvider>
  );
}
