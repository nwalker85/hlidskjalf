import { NextRequest, NextResponse } from 'next/server';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { message, thread_id } = body;

    // Call the Hlidskjalf API
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'https://hlidskjalf-api.ravenhelm.test';
    
    const response = await fetch(`${apiUrl}/api/v1/norns/chat`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        message,
        thread_id,
      }),
    });

    if (!response.ok) {
      throw new Error(`API error: ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
    
  } catch (error) {
    console.error('Norns chat error:', error);
    return NextResponse.json(
      { error: 'Failed to communicate with the Norns' },
      { status: 500 }
    );
  }
}

