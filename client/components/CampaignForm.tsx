
'use client';

import { useState } from 'react';
import { Loader2, Plus } from 'lucide-react';

export default function CampaignForm({ onCreated }: { onCreated: () => void }) {
    const [loading, setLoading] = useState(false);
    const [name, setName] = useState('');
    const [message, setMessage] = useState('');
    const [scheduledAt, setScheduledAt] = useState('');
    const [type, setType] = useState<'message' | 'status'>('message');
    const [audienceType, setAudienceType] = useState<'all' | 'selected'>('all');
    const [contacts, setContacts] = useState<{ id: string, name: string }[]>([]);
    const [selectedContacts, setSelectedContacts] = useState<string[]>([]);
    const [showContactSelector, setShowContactSelector] = useState(false);

    const fetchContacts = async () => {
        try {
            const res = await fetch('http://localhost:3001/api/whatsapp/contacts');
            if (res.ok) {
                const data = await res.json();
                setContacts(data);
                setShowContactSelector(true);
            }
        } catch (error) {
            console.error('Failed to fetch contacts', error);
        }
    };

    const handleAudienceChange = (val: 'all' | 'selected') => {
        setAudienceType(val);
        if (val === 'selected' && contacts.length === 0) {
            fetchContacts();
        } else if (val === 'selected') {
            setShowContactSelector(true);
        } else {
            setShowContactSelector(false);
        }
    };

    const toggleContact = (id: string) => {
        setSelectedContacts(prev =>
            prev.includes(id) ? prev.filter(c => c !== id) : [...prev, id]
        );
    };

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
                    type,
                    audience_type: audienceType,
                    selected_contacts: audienceType === 'selected' ? selectedContacts : [],
                    scheduled_at: scheduledAt ? new Date(scheduledAt).toISOString() : new Date().toISOString()
                })
            });

            if (res.ok) {
                setName('');
                setMessage('');
                setScheduledAt('');
                setType('message');
                setAudienceType('all');
                setSelectedContacts([]);
                onCreated();
            }
        } catch (error) {
            console.error('Failed to create campaign', error);
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="p-4 bg-[var(--wa-panel-bg)] rounded-lg space-y-4">
            <h3 className="text-lg font-medium text-[var(--wa-text-primary)] mb-4">New Campaign</h3>

            <div className='flex gap-4 mb-4'>
                <label className='flex items-center gap-2 text-[var(--wa-text-primary)]'>
                    <input
                        type="radio"
                        name="type"
                        checked={type === 'message'}
                        onChange={() => setType('message')}
                        className="accent-[var(--wa-primary)]"
                    />
                    Message
                </label>
                <label className='flex items-center gap-2 text-[var(--wa-text-primary)]'>
                    <input
                        type="radio"
                        name="type"
                        checked={type === 'status'}
                        onChange={() => setType('status')}
                        className="accent-[var(--wa-primary)]"
                    />
                    Status
                </label>
            </div>

            <input
                type="text"
                placeholder="Campaign Name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-[var(--wa-bg)] border-none rounded p-3 text-[var(--wa-text-primary)] focus:ring-1 focus:ring-[var(--wa-primary)] mb-4"
                required
            />

            <textarea
                placeholder={type === 'status' ? "Status Text" : "Message (use {name} for variable)"}
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                className="w-full bg-[var(--wa-bg)] border-none rounded p-3 text-[var(--wa-text-primary)] h-32 resize-none focus:ring-1 focus:ring-[var(--wa-primary)] mb-4"
                required
            />

            {type === 'message' && (
                <div className='mb-4'>
                    <label className="text-xs text-[var(--wa-text-secondary)] mb-2 block">Audience</label>
                    <div className='flex gap-4 mb-2'>
                        <label className='flex items-center gap-2 text-[var(--wa-text-primary)]'>
                            <input
                                type="radio"
                                name="audience"
                                checked={audienceType === 'all'}
                                onChange={() => handleAudienceChange('all')}
                                className="accent-[var(--wa-primary)]"
                            />
                            All Contacts
                        </label>
                        <label className='flex items-center gap-2 text-[var(--wa-text-primary)]'>
                            <input
                                type="radio"
                                name="audience"
                                checked={audienceType === 'selected'}
                                onChange={() => handleAudienceChange('selected')}
                                className="accent-[var(--wa-primary)]"
                            />
                            Selected Contacts
                        </label>
                    </div>

                    {audienceType === 'selected' && (
                        <div className="max-h-40 overflow-y-auto bg-[var(--wa-bg)] rounded p-2 border border-[var(--wa-border)]">
                            {contacts.length === 0 ? <p className="text-[var(--wa-text-secondary)] text-sm">Loading contacts...</p> :
                                contacts.map(c => (
                                    <label key={c.id} className="flex items-center gap-2 p-1 hover:bg-[var(--wa-panel-bg)] rounded cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={selectedContacts.includes(c.id)}
                                            onChange={() => toggleContact(c.id)}
                                            className="accent-[var(--wa-primary)]"
                                        />
                                        <span className="text-sm text-[var(--wa-text-primary)]">{c.name || c.id}</span>
                                    </label>
                                ))
                            }
                        </div>
                    )}
                </div>
            )}

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
                onClick={handleSubmit}
                disabled={loading}
                className="w-full bg-[var(--wa-primary)] hover:bg-[#00a884] text-black font-medium p-3 rounded flex items-center justify-center gap-2 transition-colors disabled:opacity-50 mt-4"
            >
                {loading ? <Loader2 className="animate-spin" /> : <Plus size={20} />}
                Create Campaign
            </button>
        </div>
    );
}
