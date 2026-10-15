import {timingSafeEqual} from 'node:crypto';
import {eveChannel} from 'eve/channels/eve';
import {localDev, type AuthFn} from 'eve/channels/auth';
const service:AuthFn<Request>=async(request)=>{
 const expected=process.env.ECHO_AGENT_TOKEN;
 const supplied=request.headers.get('authorization')?.replace(/^Bearer /,'');
 const principal=request.headers.get('x-echo-user');
 if(!expected||expected.length<32||!supplied||!principal||principal.length>200)return null;
 const a=Buffer.from(expected),b=Buffer.from(supplied);
 if(a.length!==b.length||!timingSafeEqual(a,b))return null;
 return {authenticator:'echo-private-site',principalId:principal,principalType:'user',attributes:{}};
};
export default eveChannel({auth:[service,localDev()]});
