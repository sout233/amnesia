import { supabase } from './supabaseClient';

export interface UserRecord {
	username: string;
	password?: string;
	role: 'root' | '管理员' | '用户';
}

export async function getUsers(): Promise<UserRecord[]> {
	try {
		const { data, error } = await supabase
			.from('amnesia_users')
			.select('username, role')
			.order('id', { ascending: true });

		if (error) throw error;
		return (data || []) as UserRecord[];
	} catch (err: any) {
		console.error('getUsers error:', err.message);
		// 发生错误时提供硬编码 sout 兜底，保障界面不崩溃
		return [{ username: 'sout', role: 'root' }];
	}
}

// 供登录验证时获取用户名与密码匹配使用
export async function verifyUser(username: string, password: string): Promise<UserRecord | null> {
	try {
		const { data, error } = await supabase
			.from('amnesia_users')
			.select('username, password, role')
			.eq('username', username)
			.eq('password', password)
			.maybeSingle();

		if (error) throw error;
		return data as UserRecord | null;
	} catch (err: any) {
		console.error('verifyUser error:', err.message);
		return null;
	}
}

export async function addUser(user: UserRecord): Promise<{ success: boolean; message: string }> {
	try {
		// 校验是否已存在该用户名
		const { data: existing, error: checkError } = await supabase
			.from('amnesia_users')
			.select('username')
			.eq('username', user.username)
			.maybeSingle();

		if (checkError) throw checkError;
		if (existing) {
			return { success: false, message: '该用户名已存在' };
		}

		const { error } = await supabase
			.from('amnesia_users')
			.insert([user]);

		if (error) throw error;
		return { success: true, message: '用户添加成功' };
	} catch (err: any) {
		console.error('addUser error:', err.message);
		return { success: false, message: '添加用户失败: ' + err.message };
	}
}

export async function deleteUser(username: string): Promise<{ success: boolean; message: string }> {
	if (username === 'sout') {
		return { success: false, message: '系统限制：无法删除默认管理员' };
	}
	try {
		const { error } = await supabase
			.from('amnesia_users')
			.delete()
			.eq('username', username);

		if (error) throw error;
		return { success: true, message: '用户已成功删除' };
	} catch (err: any) {
		console.error('deleteUser error:', err.message);
		return { success: false, message: '删除用户失败: ' + err.message };
	}
}
