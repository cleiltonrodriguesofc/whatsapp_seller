
'use client';

import { useState } from 'react';
import { Loader2, Plus } from 'lucide-react';

export default function CampaignForm({ onCreated }: { onCreated: () => void }) {
    const [loading, setLoading] = useState(false);
    const [name, setName] = useState('');
    const [message, setMessage] = useState('');
    const [scheduledAt, setScheduledAt] = useState('');

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setLoading(true);

        try {
            const res = await fetch('http://localhost:3001/api/campaigns', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name,
                    message,
                    scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : new Date().toISOString()
                })
            });

            if (res.ok) {
                setName('');
                setMessage('');
                setScheduledAt('');
                onCreated();
            }
        } catch (error) {
            console.error('Failed to create campaign', error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <form onSubmit={handleSubmit} className="p-4 bg-[var(--wa-panel-bg)] rounded-lg space-y-4">
            <h3 className="text-lg font-medium text-[var(--wa-text-primary)] mb-4">New Campaign</h3>

            <div>
                <input
                    type="text"
                    placeholder="Campaign Name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full bg-[var(--wa-bg)] border-none rounded p-3 text-[var(--wa-text-primary)] focus:ring-1 focus:ring-[var(--wa-primary)]"
                    required
                />
            </div>

            <div>
                <textarea
                    placeholder="Message (use {name} for variable)"
                    value={message}
                    onChange={(e) => setMessage(e.target.value)}
                    className="w-full bg-[var(--wa-bg)] border-none rounded p-3 text-[var(--wa-text-primary)] h-32 resize-none focus:ring-1 focus:ring-[var(--wa-primary)]"
                    required
                />
            </div>

            <div>
                <label className="text-xs text-[var(--wa-text-secondary)] mb-1 block">Schedule (Optional)</label>
                <input
                    type="datetime-local"
                    value={scheduledAt}
                    onChange={(e) => setScheduledAt(e.target.value)}
                    className="w-full bg-[var(--wa-bg)] border-none rounded p-3 text-[var(--wa-text-primary)] focus:ring-1 focus:ring-[var(--wa-primary)]"
                />
            </div>

            <button
                type="submit"
                disabled={loading}
                className="w-full bg-[var(--wa-primary)] hover:bg-[#00a884] text-black font-medium p-3 rounded flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
            >
                {loading ? <Loader2 className="animate-spin" /> : <Plus size={20} />}
                Create Campaign
            </button>
        </form>
    );
}
