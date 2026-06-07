#import <Foundation/Foundation.h>
#import <UIKit/UIKit.h>
#import <objc/runtime.h>

// ====================================================
// DaimonTweak - يضيف ميزة التخصيص لتطبيق Daimon
// الشخصية تُجلب من: /daimon-config/get على السيرفر
// ====================================================

#define RAILWAY_URL @"https://web-production-2abe3.up.railway.app"

static NSString *g_persona = @"";
static IMP originalDataTaskIMP = NULL;
static IMP originalUploadTaskIMP = NULL;

// ---- جلب الشخصية من السيرفر ----
static void fetchPersonaFromServer(void) {
    NSURL *url = [NSURL URLWithString:RAILWAY_URL @"/daimon-config/get"];
    NSURLSession *session = [NSURLSession sharedSession];
    dispatch_semaphore_t sem = dispatch_semaphore_create(0);

    [[session dataTaskWithURL:url completionHandler:^(NSData *data, NSURLResponse *resp, NSError *err) {
        if (data && !err) {
            NSDictionary *json = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
            NSString *p = json[@"persona"];
            if (p && p.length > 0) {
                g_persona = [p copy];
            }
        }
        dispatch_semaphore_signal(sem);
    }] resume];

    dispatch_semaphore_wait(sem, dispatch_time(DISPATCH_TIME_NOW, 3 * NSEC_PER_SEC));
}

// ---- تعديل الـ Request لإضافة الشخصية ----
static NSURLRequest *injectPersona(NSURLRequest *request) {
    if (g_persona.length == 0) return request;

    NSString *method = request.HTTPMethod;
    BOOL isModifiable = [@[@"POST", @"PUT", @"PATCH"] containsObject:method];
    if (!isModifiable) return request;

    NSData *body = request.HTTPBody;
    if (!body || body.length == 0) return request;

    NSError *err;
    NSMutableDictionary *json = [[NSJSONSerialization JSONObjectWithData:body
                                                                options:NSJSONReadingMutableContainers
                                                                  error:&err] mutableCopy];
    if (!json || err) return request;

    json[@"interaction_instructions"] = g_persona;
    json[@"interactionInstructions"]  = g_persona;

    NSData *newBody = [NSJSONSerialization dataWithJSONObject:json options:0 error:nil];
    if (!newBody) return request;

    NSMutableURLRequest *mReq = [request mutableCopy];
    mReq.HTTPBody = newBody;
    [mReq setValue:[NSString stringWithFormat:@"%lu", (unsigned long)newBody.length]
        forHTTPHeaderField:@"Content-Length"];
    return [mReq copy];
}

// ---- Swizzle: dataTaskWithRequest:completionHandler: ----
static NSURLSessionDataTask *hooked_dataTask(id self, SEL _cmd,
                                              NSURLRequest *request,
                                              void (^handler)(NSData *, NSURLResponse *, NSError *)) {
    request = injectPersona(request);
    typedef NSURLSessionDataTask *(*Fn)(id, SEL, NSURLRequest *, void (^)(NSData *, NSURLResponse *, NSError *));
    return ((Fn)originalDataTaskIMP)(self, _cmd, request, handler);
}

// ---- Constructor ----
__attribute__((constructor))
static void DaimonTweakInit(void) {
    // جلب الشخصية في الخلفية
    dispatch_async(dispatch_get_global_queue(DISPATCH_QUEUE_PRIORITY_HIGH, 0), ^{
        fetchPersonaFromServer();
    });

    // تطبيق الـ swizzle بعد ثانية واحدة
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, (int64_t)(1.0 * NSEC_PER_SEC)),
                   dispatch_get_main_queue(), ^{
        Class cls = objc_getClass("__NSCFURLSessionConfiguration") ?: [NSURLSession class];
        // نحاول الـ class الصح
        cls = [NSURLSession class];
        SEL sel = @selector(dataTaskWithRequest:completionHandler:);
        Method m = class_getInstanceMethod(cls, sel);
        if (m) {
            originalDataTaskIMP = method_getImplementation(m);
            method_setImplementation(m, (IMP)hooked_dataTask);
        }
    });
}
