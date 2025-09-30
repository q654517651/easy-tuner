import { HeroUIProvider } from '@heroui/react';
import {ToastProvider} from "@heroui/toast";
import { ReadinessProvider } from './contexts/ReadinessContext';

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <HeroUIProvider>
      <ToastProvider/>
      <ReadinessProvider>
        {children}
      </ReadinessProvider>
    </HeroUIProvider>
  );
}
