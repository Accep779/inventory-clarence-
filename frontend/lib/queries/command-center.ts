import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '../api';
import { useAuth } from '../context/MerchantContext';

// --- Types ---

export interface Skill {
    name: string;
    description: string;
    active: boolean;
    tool_count: number;
}

export interface SkillListResponse {
    skills: Skill[];
    count: number;
}

export interface ChannelConfig {
    channel_id: string;
    provider: string;
    status: string;
    is_active: boolean;
}

export interface GatewayResponse {
    channels: ChannelConfig[];
}

export interface QueueItem {
    id: string;
    priority: string;
    channel: string;
    topic: string;
    content: string;
    created_at: string;
}

export interface DigestQueueResponse {
    queue_size: number;
    items: QueueItem[];
}

// --- Hooks ---

/**
 * Fetch available Agent Skills.
 */
export const useSkills = () => {
    const { isAuthenticated } = useAuth();

    return useQuery({
        queryKey: ['skills'],
        queryFn: async () => {
            const { data } = await api.get('/skills/');
            return data as SkillListResponse;
        },
        enabled: isAuthenticated,
    });
};

/**
 * Toggle a Skill (Enable/Disable).
 */
export const useSkillToggle = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async ({ skillName, active }: { skillName: string; active: boolean }) => {
            const { data } = await api.post(`/skills/${skillName}/toggle`, null, {
                params: { active }
            });
            return data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['skills'] });
        },
    });
};

/**
 * Fetch Gateway Channels.
 */
export const useGatewayConfig = () => {
    const { isAuthenticated } = useAuth();

    return useQuery({
        queryKey: ['gateway-channels'],
        queryFn: async () => {
            const { data } = await api.get('/gateway/channels');
            return data as GatewayResponse;
        },
        enabled: isAuthenticated,
    });
};

/**
 * Update Gateway Channel Config (Stub for API Keys).
 */
export const useGatewayUpdate = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async ({ channelId, config }: { channelId: string; config: any }) => {
            const { data } = await api.patch(`/gateway/channels/${channelId}`, config);
            return data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['gateway-channels'] });
        },
    });
};

/**
 * Fetch Digest Queue (Pending Notifications).
 */
export const useDigestQueue = () => {
    const { isAuthenticated } = useAuth();

    return useQuery({
        queryKey: ['digest-queue'],
        queryFn: async () => {
            const { data } = await api.get('/digest/queue');
            return data as DigestQueueResponse;
        },
        enabled: isAuthenticated,
        refetchInterval: 10000, // Refresh every 10s to show incoming spam blocks
    });
};

/**
 * Flush Digest (Force Send).
 */
export const useDigestFlush = () => {
    const queryClient = useQueryClient();

    return useMutation({
        mutationFn: async () => {
            const { data } = await api.post('/digest/flush');
            return data;
        },
        onSuccess: () => {
            queryClient.invalidateQueries({ queryKey: ['digest-queue'] });
            // Also invalidate inbox as the summary might appear there
            queryClient.invalidateQueries({ queryKey: ['inbox'] });
        },
    });
};
