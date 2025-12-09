
export interface Campaign {
    id: number;
    name: string;
    message: string;
    status: 'pending' | 'processing' | 'completed' | 'paused';
    type: 'message' | 'status';
    scheduled_at: string;
    created_at: string;
}
