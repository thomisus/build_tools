exports.handlers = {
    processingComplete: function(e) {
        // array for filtered doclets
        let filteredDoclets = [];

        const cleanName = name => name ? name.replace('<anonymous>~', '').replaceAll('"', '') : name;

        const classesDocletsMap = {}; // doclets for classes write at the end
        let passedClasses = []; // passed classes for current editor
        let passedClassesWithDirectMethods = []; // passed classes that have at least one direct (non-inherited) method for this editor

        const isTransitiveAncestor = (cls, target) => {
            const doclet = classesDocletsMap[cls];
            if (!doclet || !doclet.augments) return false;
            if (doclet.augments.includes(target)) return true;
            return doclet.augments.some(parent => isTransitiveAncestor(parent, target));
        };

        // JSDoc only generates inherited doclets one level deep (B←C), so A←B←C is missing.
        // Pre-generate transitive inherited doclets before any filtering.
        {
            const classAugmentsMap = {};
            const classMethodsMap = {};

            e.doclets.forEach(doclet => {
                if (doclet.kind === 'class') {
                    const name = cleanName(doclet.name);
                    classAugmentsMap[name] = doclet.augments || [];
                    if (!classMethodsMap[name]) classMethodsMap[name] = [];
                }
                if ((doclet.kind === 'function' || doclet.kind === 'method') && doclet.memberof) {
                    const cls = cleanName(doclet.memberof);
                    if (!classMethodsMap[cls]) classMethodsMap[cls] = [];
                    classMethodsMap[cls].push(doclet);
                }
            });

            const visited = new Set();
            const order = [];
            const visit = (cls) => {
                if (visited.has(cls)) return;
                visited.add(cls);
                for (const parent of (classAugmentsMap[cls] || [])) visit(parent);
                order.push(cls);
            };
            Object.keys(classAugmentsMap).forEach(visit);

            const newDoclets = [];
            for (const cls of order) {
                for (const parent of (classAugmentsMap[cls] || [])) {
                    const parentMethods = classMethodsMap[parent] || [];
                    const clsMethodNames = new Set((classMethodsMap[cls] || []).map(m => cleanName(m.name)));

                    for (const method of parentMethods) {
                        const methodName = cleanName(method.name);
                        if (!clsMethodNames.has(methodName)) {
                            const inherited = {
                                ...method,
                                memberof: cls,
                                longname: `${cls}#${methodName}`,
                                inherited: true,
                                inherits: method.inherited ? method.inherits : `${parent}#${methodName}`,
                            };
                            newDoclets.push(inherited);
                            if (!classMethodsMap[cls]) classMethodsMap[cls] = [];
                            classMethodsMap[cls].push(inherited);
                            clsMethodNames.add(methodName);
                        }
                    }
                }
            }

            e.doclets.push(...newDoclets);
        }

        // Remove dublicates doclets
        const latestDoclets = {};
        e.doclets.forEach(doclet => {
            const isMethod = doclet.kind === 'function' || doclet.kind === 'method';
            const hasTypeofEditorsTag = isMethod && doclet.tags && doclet.tags.some(tag => tag.title === 'typeofeditors' && tag.value.includes(process.env.EDITOR));

            const shouldAddMethod = 
                doclet.kind !== 'member' &&
                (!doclet.longname || doclet.longname.search('private') === -1) &&
                doclet.scope !== 'inner' && hasTypeofEditorsTag;

            if (shouldAddMethod || doclet.kind == 'typedef' || doclet.kind == 'class') {
                latestDoclets[doclet.longname] = doclet;
            }
        });
        e.doclets.splice(0, e.doclets.length, ...Object.values(latestDoclets));

        // check available classess for current editor
        for (let i = 0; i < e.doclets.length; i++) {
            const doclet = e.doclets[i];
            const isMethod = doclet.kind === 'function' || doclet.kind === 'method';
            const hasTypeofEditorsTag = isMethod && doclet.tags && doclet.tags.some(tag => tag.title === 'typeofeditors' && tag.value.includes(process.env.EDITOR));

            const shouldAdd = 
                doclet.kind !== 'member' &&
                (!doclet.longname || doclet.longname.search('private') === -1) &&
                doclet.scope !== 'inner' &&
                (!isMethod || hasTypeofEditorsTag);

            if (shouldAdd) {
                if (doclet.memberof) {
                    const className = cleanName(doclet.memberof);
                    if (false == passedClasses.includes(className)) {
                        passedClasses.push(className);
                    }
                    if (!doclet.inherited && false == passedClassesWithDirectMethods.includes(className)) {
                        passedClassesWithDirectMethods.push(className);
                    }
                }
            }
            else if (doclet.kind == 'class') {
                classesDocletsMap[cleanName(doclet.name)] = doclet;
            }
        }

        // remove unavailave classes in current editor
        passedClasses = passedClasses.filter(className => {
            const classDoclet = classesDocletsMap[className];
            if (!classDoclet) {
                // no explicit class definition — allow only if it has direct (non-inherited) methods for this editor
                return passedClassesWithDirectMethods.includes(className);
            }

            const hasTypeofEditorsTag = !!(classDoclet.tags && classDoclet.tags.some(tag => tag.title === 'typeofeditors'));
            if (hasTypeofEditorsTag) {
                return classDoclet.tags.some(tag => tag.title === 'typeofeditors' && tag.value && tag.value.includes(process.env.EDITOR));
            }

            // no editor tag on class — allow only if it has direct (non-inherited) methods for this editor
            return passedClassesWithDirectMethods.includes(className);
        });

        for (let i = 0; i < e.doclets.length; i++) {
            const doclet = e.doclets[i];
            const isMethod = doclet.kind === 'function' || doclet.kind === 'method';
            const hasTypeofEditorsTag = isMethod && doclet.tags && doclet.tags.some(tag => tag.title === 'typeofeditors' && tag.value.includes(process.env.EDITOR));

            let shouldAddMethod = 
                doclet.kind !== 'member' &&
                (!doclet.longname || doclet.longname.search('private') === -1) &&
                doclet.scope !== 'inner' && hasTypeofEditorsTag;

			// class names may be the same between editors, we check against the inheritance tree
			if (doclet.inherits) {
				const parentClass = doclet.inherits.split('#')[0];
				const curClass = cleanName(doclet.memberof);

				if (!isTransitiveAncestor(curClass, parentClass)) {
					shouldAddMethod = false;
				}
			}

            if (shouldAddMethod) {
                // if the class is not in our map, then we deleted it ourselves -> not available in the editor
                if (false == passedClasses.includes(cleanName(doclet.memberof))) {
                    continue;
                }

                // We leave only the necessary fields
                doclet.memberof = cleanName(doclet.memberof);
                doclet.longname = cleanName(doclet.longname);
                doclet.name     = cleanName(doclet.name);

                // skip inherited methods if ovveriden in child class
                if (doclet.inherited && filteredDoclets.find((addedDoclet) => addedDoclet['name'] == doclet['name'] && addedDoclet['memberof'] == doclet['memberof'])) {
                    continue;
                }

                const filteredDoclet = {
                    comment:        doclet.comment,
                    description:    doclet.description,
                    memberof:       cleanName(doclet.memberof),

                    params: doclet.params ? doclet.params.map(param => ({
                        type: param.type ? {
                            names:      param.type.names,
                            parsedType: param.type.parsedType
                        } : param.type,

                        name:           param.name,
                        description:    param.description,
                        optional:       param.optional,
                        defaultvalue:   param.defaultvalue
                    })) : doclet.params,

                    returns: doclet.returns ? doclet.returns.map(returnObj => ({
                        type: {
                          names:        returnObj.type.names,
                          parsedType:   returnObj.type.parsedType
                        }
                    })) : doclet.returns,

                    name:           doclet.name,
                    longname:       cleanName(doclet.longname),
                    kind:           doclet.kind,
                    scope:          doclet.scope,

                    type: doclet.type ? {
                        names: doclet.type.names,
                        parsedType: doclet.type.parsedType
                    } : doclet.type,
                    
                    properties: doclet.properties ? doclet.properties.map(property => ({
                        type: property.type ? {
                            names:      property.type.names,
                            parsedType: property.type.parsedType
                        } : property.type,

                        name:           property.name,
                        description:    property.description,
                        optional:       property.optional,
                        defaultvalue:   property.defaultvalue
                    })) : doclet.properties,
                    
                    meta: doclet.meta ? {
                        lineno:   doclet.meta.lineno,
                        columnno: doclet.meta.columnno
                    } : doclet.meta,

                    see:      doclet.see,
                    inherited: doclet.inherited,
                    inherits:  doclet.inherits
                };

                // Add the filtered doclet to the array
                filteredDoclets.push(filteredDoclet);
            }
            else if (doclet.kind == 'class') {
                // if the class is not in our map, then we deleted it ourselves -> not available in the editor
                if (false == passedClasses.includes(cleanName(doclet.name))) {
                    continue;
                }

                const filteredDoclet = {
                    comment:        doclet.comment,
                    description:    doclet.description,
                    name:           cleanName(doclet.name),
                    longname:       cleanName(doclet.longname),
                    kind:           doclet.kind,
                    scope:          "global",
                    augments:       doclet.augments || undefined,
                    meta: doclet.meta ? {
                        lineno:   doclet.meta.lineno,
                        columnno: doclet.meta.columnno
                    } : doclet.meta,
                    properties: doclet.properties ? doclet.properties.map(property => ({
                        type: property.type ? {
                            names:      property.type.names,
                            parsedType: property.type.parsedType
                        } : property.type,

                        name:           property.name,
                        description:    property.description,
                        optional:       property.optional,
                        defaultvalue:   property.defaultvalue
                    })) : doclet.properties,
                    see: doclet.see || undefined
                };
    
                filteredDoclets.push(filteredDoclet);
            }
            else if (doclet.kind == 'typedef') {
                const filteredDoclet = {
                    comment:        doclet.comment,
                    description:    doclet.description,
                    name:           cleanName(doclet.name),
                    longname:       cleanName(doclet.longname),
                    kind:           doclet.kind,
                    scope:          "global",

                    meta: doclet.meta ? {
                        lineno:   doclet.meta.lineno,
                        columnno: doclet.meta.columnno
                    } : doclet.meta,

                    properties: doclet.properties ? doclet.properties.map(property => ({
                        type: property.type ? {
                            names:      property.type.names,
                            parsedType: property.type.parsedType
                        } : property.type,

                        name:           property.name,
                        description:    property.description,
                        optional:       property.optional,
                        defaultvalue:   property.defaultvalue
                    })) : doclet.properties,

                    see: doclet.see,
                    type: doclet.type ? {
                        names: doclet.type.names,
                        parsedType: doclet.type.parsedType
                    } : doclet.type
                };

                filteredDoclets.push(filteredDoclet);
            }
        }

        // Replace doclets with a filtered array
        e.doclets.splice(0, e.doclets.length, ...filteredDoclets);
    }
};
