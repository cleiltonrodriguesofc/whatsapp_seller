
'use client';

import { useEffect, useState } from 'react';
import { Campaign } from '@/types/campaign';
import { Clock, CheckCircle, AlertCircle, RefreshCw } from 'lucide-react';

export default function CampaignList({ refreshTrigger }: { refreshTrigger: number }) {
    const [campaigns, setCampaigns] = useState<Campaign[]>([]);

    useEffect(() => {
        fetch('http://localhost:3001/api/campaigns')
            .then(res => res.json())
            .then(data => setCampaigns(data))
            .catch(err => console.error(err));
    }, [refreshTrigger]);

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'completed': return <CheckCircle size={16} className="text-green-500" />;
            case 'pending': return <Clock size={16} className="text-yellow-500" />;
            case 'processing': return <RefreshCw size={16} className="animate-spin text-blue-500" />;
            default: return <AlertCircle size={16} className="text-gray-500" />;
        }
    };

    return (
        <div className="flex flex-col gap-2 mt-4">
            {campaigns.map(campaign => (
                <div key={campaign.id} className="bg-[var(--wa-panel-bg)] p-4 rounded-lg flex justify-between items-center border-b border-gray-800 last:border-0 hover:bg-[#202c33] cursor-pointer transition-colors">
                    <div>
                        <h4 className="text-[var(--wa-text-primary)] font-medium">{campaign.name}</h4>
                        <p className="text-[var(--wa-text-secondary)] text-sm truncate max-w-[300px]">{campaign.message}</p>
                        <p className="text-xs text-gray-500 mt-1">
                            {new Date(campaign.scheduled_at).toLocaleString()}
                        </p>
                    </div>
                    <div className="flex items-center gap-2">
                        <span className="text-xs uppercase tracking-wider text-[var(--wa-text-secondary)]">
                            {campaign.status}
                        </span>
                        {getStatusIcon(campaign.status)}
                    </div>
                </div>
            ))}
            {campaigns.length === 0 && (
                <p className="text-center text-[var(--wa-text-secondary)] py-8">No campaigns found.</p>
            )}
        </div>
    );
}
