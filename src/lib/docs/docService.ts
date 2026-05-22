import { supabase } from '$lib/supabaseClient';
import type { DocRecord, DocSpaceType, EntityId } from '$lib/types/domain';

async function listUserTeamIds(userId: EntityId) {
	const { data, error } = await supabase
		.from('amnesia_team_members')
		.select('team_id')
		.eq('user_id', userId);

	if (error) throw error;
	return (data ?? []).map((row) => row.team_id).filter(Boolean);
}

export async function listAccessibleDocs(userId: EntityId) {
	const teamIds = await listUserTeamIds(userId);
	const visibilityFilters = [`space_type.eq.global`, `owner_user_id.eq.${userId}`];

	if (teamIds.length > 0) {
		visibilityFilters.push(`and(space_type.eq.team,team_id.in.(${teamIds.join(',')}))`);
	}

	const { data, error } = await supabase
		.from('amnesia_docs')
		.select('*')
		.or(visibilityFilters.join(','))
		.order('updated_at', { ascending: false });

	if (error) throw error;
	return (data ?? []) as DocRecord[];
}

export async function createDoc(input: {
	title: string;
	emoji: string;
	category: string;
	content: string;
	author: string;
	ownerUserId?: EntityId | null;
	teamId?: EntityId | null;
	spaceType: DocSpaceType;
	settings?: Record<string, unknown>;
	isEncrypted?: boolean;
	encryptionVersion?: number;
}) {
	const { data, error } = await supabase
		.from('amnesia_docs')
		.insert({
			title: input.title,
			emoji: input.emoji,
			category: input.category,
			content: input.content,
			author: input.author,
			owner_user_id: input.ownerUserId ?? null,
			team_id: input.teamId ?? null,
			space_type: input.spaceType,
			is_encrypted: input.isEncrypted ?? false,
			encryption_version: input.encryptionVersion ?? 1,
			settings: input.settings ?? {}
		})
		.select()
		.single();

	if (error) throw error;
	return data as DocRecord;
}

export async function updateDoc(input: {
	id: number;
	title?: string;
	content?: string;
	emoji?: string;
	category?: string;
	settings?: Record<string, unknown>;
	isEncrypted?: boolean;
	encryptionVersion?: number;
}) {
	const patch: Record<string, unknown> = {};
	if (input.title !== undefined) patch.title = input.title;
	if (input.content !== undefined) patch.content = input.content;
	if (input.emoji !== undefined) patch.emoji = input.emoji;
	if (input.category !== undefined) patch.category = input.category;
	if (input.settings !== undefined) patch.settings = input.settings;
	if (input.isEncrypted !== undefined) patch.is_encrypted = input.isEncrypted;
	if (input.encryptionVersion !== undefined) patch.encryption_version = input.encryptionVersion;

	const { data, error } = await supabase
		.from('amnesia_docs')
		.update(patch)
		.eq('id', input.id)
		.select()
		.single();

	if (error) throw error;
	return data as DocRecord;
}
