
import asyncio
import os
from core.db_async import AsyncDatabase
from core.registry import Registry
from core.orm import Model
from core.fields import Char, Many2one
from core.env import Environment

class DxArtist(Model):
    _name = 'dx.artist'
    name = Char()

class DxSong(Model):
    _name = 'dx.song'
    title = Char()
    artist_id = Many2one('dx.artist', string='Artist')

Registry.register('dx.artist', DxArtist)
Registry.register('dx.song', DxSong)

async def test_dx():
    print("Initializing DB...")
    await AsyncDatabase.initialize()
    
    async with AsyncDatabase.acquire() as cr:
        # Tables
        await DxArtist._auto_init(cr)
        await DxSong._auto_init(cr)
        
        env = Environment(cr, uid=1, context={})
        
        # Create Data
        artist = await env['dx.artist'].create({'name': 'Daft Punk'})
        song = await env['dx.song'].create({
            'title': 'Get Lucky',
            'artist_id': artist.id
        })
        
        print("Test 1: Await RecordSet (Cached)")
        # 'artist' is fully cached because create returns it.
        # Check explicit await call
        res = await artist
        print(f"Await result: {res}")
        if res == artist:
            print("PASS: Awaiting RecordSet works.")
        else:
            print("FAIL: Awaiting RecordSet returned something else.")

        print("Test 2: Lazy Load Relation (Uncached)")
        # Clear cache to simulate fresh read
        env.cache.clear()
        
        # Get fresh record (only ID known if we used search, but here we construct)
        # Let's search to simulate cold start
        song_rec = (await env['dx.song'].search([('id', '=', song.id)]))[0]
        
        # Access song_rec.artist_id
        # It is NOT in cache (search only fetches ID by default usually, unless eager logic changed)
        # Wait, search returns RecordSet. Accessing fields triggers __get__.
        # artist_id is uncached. 
        # Should return FieldFuture.
        
        future = song_rec.artist_id
        print(f"Access returned: {future}")
        
        if 'FieldFuture' in str(future):
            print("PASS: FieldFuture returned.")
        else:
            print("FAIL: FieldFuture not returned (maybe cached?).")
            
        # Await it
        artist_rel = await song_rec.artist_id
        print(f"Resolved: {artist_rel}")
        
        # Verify it is the artist
        # Accessing name requires another await if not fetched?
        # Typically 'ensure' fetches default fields? ORM default is primitive fields.
        # But 'artist_id' points to a record. Does browsing fetch data? No.
        # So 'artist_rel' is a RecordSet with ID. 
        # Its 'name' is NOT cached unless we read it.
        
        # Test chaining? 'await record.partner_id' gives RecordSet.
        # 'await (await record.partner_id).name' ?
        # 'name' is Char. If not cached, it raises RuntimeError currently (as per plan).
        # So we must ensure name.
        
        await artist_rel.read(['name'])
        print(f"Artist Name: {artist_rel.name}")
        
        if artist_rel.name == 'Daft Punk':
            print("PASS: Lazy Loading Successful.")
        else:
             print("FAIL: Wrong data.")

        print("Test 3: Await Cached Relation")
        # Now artist_id is in cache (val_id).
        # __get__ should return RecordSet.
        # await RecordSet should work.
        
        cached_rel = await song_rec.artist_id
        print(f"Cached Await: {cached_rel}")
        if cached_rel.id == artist.id:
             print("PASS: Awaiting Cached Relation works.")
        else:
             print("FAIL: Cached Relation broken.")

    await AsyncDatabase.close()

if __name__ == "__main__":
    asyncio.run(test_dx())
