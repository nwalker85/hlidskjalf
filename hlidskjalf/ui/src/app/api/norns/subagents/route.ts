import { NextResponse } from 'next/server';

export async function GET() {
  try {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://hlidskjalf-api.ravenhelm.test';
    
    const response = await fetch(`${apiUrl}/api/v1/norns/subagents`, {
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
    
  } catch (error) {
    console.error('Failed to fetch subagents:', error);
    return NextResponse.json(
      { error: 'Failed to fetch subagents', subagents: [] },
      { status: 500 }
    );
  }
}

