
'use client';

import { useEffect, useState } from 'react';
import { useSocket } from '@/app/hooks/useSocket';
import { Loader2 } from 'lucide-react';

export default function ConnectionState() {
    const { socket, isConnected } = useSocket();
    const [qrCode, setQrCode] = useState<string | null>(null);
    const [status, setStatus] = useState<string>('disconnected');

    useEffect(() => {
        if (!socket) return;

        socket.on('qr', (qr: string) => {
            setQrCode(qr);
            setStatus('scan_qr');
        });

        socket.on('status', (sessionStatus: string) => {
            setStatus(sessionStatus);
            if (sessionStatus === 'inChat' || sessionStatus === 'connected') {
                setQrCode(null);
            }
        });

        socket.on('connection-status', (state: string) => {
            console.log('Connection Status:', state);
        });

    }, [socket]);

    if (!isConnected) {
        return (
            <div className="flex flex-col items-center justify-center p-4 text-[var(--wa-text-secondary)]">
                <p>Connecting to server...</p>
            </div>
        );
    }

    return (
        <div className="flex flex-col items-center justify-center p-4">
            {status === 'scan_qr' && qrCode && (
                <div className="bg-white p-2 rounded-lg">
                    <img src={qrCode} alt="WhatsApp QR Code" className="w-48 h-48" />
                </div>
            )}

            <div className="mt-4 text-[var(--wa-text-primary)] text-sm font-medium">
                Status: <span className="text-[var(--wa-primary)] uppercase">{status}</span>
            </div>

            {status === 'scan_qr' && (
                <p className="text-[var(--wa-text-secondary)] text-xs mt-2 text-center">
                    Open WhatsApp on your phone and scan the QR code.
                </p>
            )}
        </div>
    );
}
